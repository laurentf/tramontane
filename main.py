"""FastAPI application entry point with lifespan, health endpoint, CORS, and exception handlers."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.core.banner import print_banner
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import setup_logging
from app.core.middleware import RequestIDMiddleware
from app.core.rate_limit import limiter
from app.features.api import router as api_router
from supabase import acreate_client

# Configure structured logging (structlog + stdlib bridge)
setup_logging()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifecycle (startup and shutdown)."""
    settings = get_settings()

    # Create asyncpg connection pool
    try:
        app.state.pool = await asyncpg.create_pool(
            dsn=settings.database_url.get_secret_value(),
            min_size=settings.db_pool_min_size,
            max_size=settings.db_pool_max_size,
            command_timeout=settings.db_pool_command_timeout,
            max_inactive_connection_lifetime=settings.db_pool_max_inactive_lifetime,
            statement_cache_size=0,
        )
        logger.info("Database connection pool created")
    except Exception as e:
        if settings.debug:
            logger.warning("Failed to create database pool: %s", e)
            app.state.pool = None
        else:
            raise

    # Create Supabase client
    app.state.supabase_client = await acreate_client(
        supabase_url=settings.supabase_url,
        supabase_key=settings.supabase_publishable_key,
    )
    logger.info("Supabase client created")

    # Startup banner
    infra: list[tuple[str, str]] = [
        ("Database", "connected" if app.state.pool else "unavailable"),
        ("Supabase", "connected"),
    ]
    if settings.redis_url:
        infra.append(("Redis/ARQ", "configured"))

    sections: list[tuple[str, list[tuple[str, str]]]] = [
        ("Infra", infra),
        ("Routes", [("API", "/api/v1")]),
    ]

    print_banner("api", sections=sections)

    yield

    # Close pool on shutdown
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
@app.get("/health", tags=["health"], response_model=None)
async def health_check() -> dict[str, str] | JSONResponse:
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

        return {
            "status": "healthy",
            "database": "connected",
        }
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
