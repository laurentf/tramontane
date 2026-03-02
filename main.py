"""FastAPI application entry point with lifespan, health endpoint, CORS, and exception handlers."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.core.banner import print_banner
from app.core.config import get_settings
from app.core.database import create_pool
from app.core.exceptions import AppError
from app.core.logging import setup_logging
from app.core.middleware import RequestIDMiddleware
from app.core.rate_limit import limiter
from app.features.api import router as api_router
from app.features.hosts.skills import SkillLoader, SkillRegistry
from app.providers.tools.handlers import SearchToolHandler, WeatherToolHandler
from app.providers.tools.registry import ToolRegistry
from supabase import acreate_client

# Configure structured logging (structlog + stdlib bridge)
setup_logging()

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifecycle (startup and shutdown)."""
    settings = get_settings()

    # Create asyncpg connection pool
    try:
        app.state.pool = await create_pool()
        logger.info("database_pool_created")
    except Exception as e:
        if settings.debug:
            logger.warning("database_pool_creation_failed", error=str(e))
            app.state.pool = None
        else:
            raise

    # Create Supabase client
    app.state.supabase_client = await acreate_client(
        supabase_url=settings.supabase_url,
        supabase_key=settings.supabase_publishable_key,
    )
    logger.info("Supabase client created")

    # Tool registry — instantiate handlers with provider adapters
    tool_registry = ToolRegistry()

    if settings.openweather_api_key:
        from app.providers.weather.openweathermap.adapter import OpenWeatherMapAdapter

        weather_adapter = OpenWeatherMapAdapter(
            api_key=settings.openweather_api_key.get_secret_value(),
        )
        tool_registry.register(WeatherToolHandler(weather_adapter))
        logger.info("Registered tool: weather")

    if settings.tavily_api_key:
        from app.providers.search.tavily.adapter import TavilySearchAdapter

        search_adapter = TavilySearchAdapter(
            api_key=settings.tavily_api_key.get_secret_value(),
        )
        tool_registry.register(SearchToolHandler(search_adapter))
        logger.info("Registered tool: web_search")

    app.state.tool_registry = tool_registry

    # Skill registry — load YAML manifests and prompt files
    skill_manifests = SkillLoader().load_all()
    app.state.skill_registry = SkillRegistry(skill_manifests)

    # Startup banner
    infra: list[tuple[str, str]] = [
        ("Database", "connected" if app.state.pool else "unavailable"),
        ("Supabase", "connected"),
    ]
    # Create ARQ Redis pool for background jobs
    if settings.redis_url:
        try:
            from arq.connections import RedisSettings
            from arq.connections import create_pool as create_arq_pool

            app.state.arq_pool = await create_arq_pool(
                RedisSettings.from_dsn(settings.redis_url.get_secret_value())
            )
            infra.append(("Redis/ARQ", "connected"))
        except Exception as exc:
            logger.warning("arq_pool_creation_failed", error=str(exc))
            app.state.arq_pool = None
            infra.append(("Redis/ARQ", "unavailable"))
    else:
        app.state.arq_pool = None

    providers: list[tuple[str, str]] = [
        ("LLM", f"{settings.llm_provider} ({settings.llm_model})"),
        ("Embedding", f"{settings.embedding_provider} ({settings.embedding_model})"),
        ("Analyzer", f"{settings.analyzer_provider} ({settings.analyzer_model})"),
    ]
    if settings.stt_provider:
        providers.append(("STT", f"{settings.stt_provider} ({settings.stt_model})"))
    if settings.tts_provider:
        providers.append(("TTS", f"{settings.tts_provider} ({settings.tts_model})"))
    if settings.leonardo_api_key:
        providers.append(("Image", "leonardo"))
    if settings.search_provider:
        providers.append(("Search", settings.search_provider))
    if settings.weather_provider:
        providers.append(("Weather", settings.weather_provider))

    streaming: list[tuple[str, str]] = []
    if settings.icecast_url:
        streaming.append(("Icecast", settings.icecast_url))
    if settings.liquidsoap_harbor_url:
        streaming.append(("Liquidsoap", settings.liquidsoap_harbor_url))

    sections: list[tuple[str, list[tuple[str, str]]]] = [
        ("Infra", infra),
        ("Providers", providers),
    ]
    if streaming:
        sections.append(("Streaming", streaming))
    if skill_manifests:
        sections.append(("Skills", [
            (name, m.level) for name, m in sorted(skill_manifests.items())
        ]))
    sections.append(("Routes", [("API", "/api/v1")]))

    print_banner("api", sections=sections)

    yield

    # Close pools on shutdown
    if getattr(app.state, "arq_pool", None):
        await app.state.arq_pool.close()
        logger.info("ARQ Redis pool closed")
    if app.state.pool:
        await app.state.pool.close()
        logger.info("Database connection pool closed")


# Create FastAPI application
app = FastAPI(
    title="Tramontane",
    description="Tramontane API",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request ID middleware
app.add_middleware(RequestIDMiddleware)

# Rate limiting
app.state.limiter = limiter


# Exception handlers
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Handle rate limit exceeded errors."""
    return JSONResponse(
        status_code=429,
        content={"error": "Rate limit exceeded. Please try again later."},
    )


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Handle custom application errors."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.message},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Normalize Pydantic validation errors to match AppError format."""
    errors = exc.errors()
    messages = [f"{e['loc'][-1]}: {e['msg']}" for e in errors if e.get("loc")]
    return JSONResponse(
        status_code=422,
        content={"error": "; ".join(messages) or "Validation error"},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Normalize HTTPException to match AppError format."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail},
    )


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected errors."""
    logger.error("Unexpected error", exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Internal server error"},
    )


# Health endpoint
@app.get("/health", tags=["health"])
async def health_check() -> JSONResponse:
    """Health check endpoint for load balancers and monitoring."""
    if not app.state.pool:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "database": "not configured",
            },
        )

    try:
        async with app.state.pool.acquire(timeout=10) as conn:
            await conn.fetchval("SELECT 1")

        return JSONResponse(content={
            "status": "healthy",
            "database": "connected",
        })
    except Exception:
        logger.exception("Health check failed")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "database": "disconnected",
            },
        )


# Mount feature routers
app.include_router(api_router, prefix="/api/v1")
