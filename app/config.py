"""Configuration management for PESUAuth API."""


from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application settings
    app_name: str = Field("PESUAuth API", env="APP_NAME")
    app_version: str = Field("2.1.0", env="APP_VERSION")
    app_description: str = Field(
        "A simple API to authenticate PESU credentials using PESU Academy",
        env="APP_DESCRIPTION"
    )

    # Server settings
    host: str = Field("0.0.0.0", env="HOST")
    port: int = Field(5000, env="PORT")
    debug: bool = Field(False, env="DEBUG")
    reload: bool = Field(False, env="RELOAD")

    # PESU Academy settings
    pesu_academy_base_url: str = Field(
        "https://www.pesuacademy.com/Academy/",
        env="PESU_ACADEMY_BASE_URL"
    )
    pesu_academy_auth_url: str = Field(
        "https://www.pesuacademy.com/Academy/j_spring_security_check",
        env="PESU_ACADEMY_AUTH_URL"
    )
    pesu_academy_timeout: float = Field(10.0, env="PESU_ACADEMY_TIMEOUT")

    # CSRF token settings
    csrf_refresh_interval: int = Field(2700, env="CSRF_REFRESH_INTERVAL")  # 45 minutes

    # Rate limiting settings
    rate_limit_enabled: bool = Field(True, env="RATE_LIMIT_ENABLED")
    rate_limit_default: str = Field("100/hour", env="RATE_LIMIT_DEFAULT")
    rate_limit_authenticate: str = Field("20/minute", env="RATE_LIMIT_AUTHENTICATE")
    rate_limit_health: str = Field("60/minute", env="RATE_LIMIT_HEALTH")

    # Redis settings (for rate limiting and caching)
    redis_url: str = Field("redis://localhost:6379", env="REDIS_URL")
    redis_enabled: bool = Field(True, env="REDIS_ENABLED")

    # Logging settings
    log_level: str = Field("INFO", env="LOG_LEVEL")
    log_format: str = Field("json", env="LOG_FORMAT")  # json or console

    # Security settings
    cors_enabled: bool = Field(True, env="CORS_ENABLED")
    cors_allow_origins: list[str] = Field(["*"], env="CORS_ALLOW_ORIGINS")
    cors_allow_methods: list[str] = Field(["GET", "POST"], env="CORS_ALLOW_METHODS")
    cors_allow_headers: list[str] = Field(["*"], env="CORS_ALLOW_HEADERS")

    # Monitoring settings
    metrics_enabled: bool = Field(True, env="METRICS_ENABLED")
    health_check_timeout: float = Field(5.0, env="HEALTH_CHECK_TIMEOUT")

    # Profile caching settings
    profile_cache_enabled: bool = Field(True, env="PROFILE_CACHE_ENABLED")
    profile_cache_ttl: int = Field(300, env="PROFILE_CACHE_TTL")  # 5 minutes

    class Config:
        """Pydantic configuration class."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()
