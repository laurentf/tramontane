"""Application configuration with Pydantic BaseSettings."""

from functools import cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Supabase
    supabase_url: str = Field(...)
    supabase_publishable_key: str = Field(...)
    supabase_secret_key: SecretStr = Field(...)

    # Database
    database_url: SecretStr = Field(...)
    db_pool_min_size: int = Field(default=5)
    db_pool_max_size: int = Field(default=10)
    db_pool_command_timeout: float = Field(default=60.0)
    db_pool_max_inactive_lifetime: float = Field(default=300.0)

    # Admin
    admin_emails: list[str] = Field(default_factory=list)

    # Redis (optional — for ARQ workers + rate limiting)
    redis_url: SecretStr | None = Field(default=None)

    # LLM / AI
    llm_provider: str = Field(default="mistral")
    llm_model: str = Field(default="labs-mistral-small-creative")
    mistral_api_key: SecretStr | None = Field(default=None)

    # Embedding
    embedding_provider: str = Field(default="mistral")
    embedding_model: str = Field(default="mistral-embed")

    # Analyzer (structured JSON)
    analyzer_provider: str = Field(default="mistral")
    analyzer_model: str = Field(default="mistral-small-latest")

    # STT
    stt_provider: str | None = Field(default="mistral")
    stt_model: str = Field(default="voxtral-mini-latest")

    # TTS
    tts_provider: str | None = Field(default="elevenlabs")
    tts_model: str = Field(default="eleven_v3")
    elevenlabs_api_key: SecretStr | None = Field(default=None)

    # Image
    leonardo_api_key: SecretStr | None = Field(default=None)
    leonardo_webhook_secret: SecretStr | None = Field(default=None)

    # Search
    search_provider: str | None = Field(default="tavily")
    tavily_api_key: SecretStr | None = Field(default=None)

    # Weather
    weather_provider: str | None = Field(default="openweathermap")
    openweather_api_key: SecretStr | None = Field(default=None)

    # Storage
    supabase_storage_bucket: str = Field(default="media")

    # Streaming
    icecast_url: str | None = Field(default=None)
    liquidsoap_harbor_url: str | None = Field(default=None)

    # Music
    music_dir: str = Field(default="/music")

    # Station
    station_location: str = Field(default="Montpellier, France")

    # App
    debug: bool = Field(default=False)
    cors_origins: list[str] = Field(default=["http://localhost:3000"])


@cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
