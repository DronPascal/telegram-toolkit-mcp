"""
Configuration management for Telegram Toolkit MCP.

This module handles environment variables, validation, and configuration
loading for the MCP server.
"""

import os

try:
    from pydantic import BaseModel, Field, ValidationError
except ImportError:
    # Fallback for development
    BaseModel = object

    def Field(**kwargs):
        return lambda cls: cls

    ValidationError = Exception


class TelegramConfig(BaseModel):
    """Telegram API configuration."""

    api_id: int = Field(..., description="Telegram API ID from https://my.telegram.org")
    api_hash: str = Field(..., description="Telegram API Hash from https://my.telegram.org")
    session_string: str | None = Field(
        default=None, description="Telethon StringSession (auto-generated if not provided)"
    )

    model_config = {"frozen": True}


class ServerConfig(BaseModel):
    """MCP Server configuration."""

    host: str = Field(default="localhost", description="Server bind host")
    port: int = Field(default=8000, ge=1, le=65535, description="Server bind port")
    log_level: str = Field(default="INFO", description="Logging level")

    # Note: Not frozen to allow command-line overrides


class PerformanceConfig(BaseModel):
    """Performance tuning configuration."""

    flood_sleep_threshold: int = Field(
        default=60, ge=10, le=300, description="FLOOD_WAIT sleep threshold in seconds"
    )
    request_timeout: int = Field(default=30, ge=5, le=120, description="Request timeout in seconds")
    max_page_size: int = Field(default=100, ge=1, le=200, description="Maximum messages per page")

    model_config = {"frozen": True}


class ResourceConfig(BaseModel):
    """Resource management configuration."""

    temp_dir: str = Field(
        default="/tmp/mcp-resources", description="Temporary directory for NDJSON files"
    )
    resource_max_age_hours: int = Field(
        default=24, ge=1, le=168, description="Maximum age of resource files in hours"
    )
    ndjson_chunk_size: int = Field(
        default=1000, ge=100, le=10000, description="Chunk size for NDJSON processing"
    )

    model_config = {"frozen": True}


class ObservabilityConfig(BaseModel):
    """Observability configuration."""

    enable_prometheus_metrics: bool = Field(
        default=True, description="Enable Prometheus metrics collection"
    )
    enable_opentelemetry_tracing: bool = Field(
        default=True, description="Enable OpenTelemetry distributed tracing"
    )
    otlp_endpoint: str | None = Field(default=None, description="OTLP endpoint for trace export")
    otlp_exporter: str = Field(
        default="grpc", description="OTLP exporter type: 'grpc', 'http', or 'jaeger'"
    )
    service_name: str = Field(
        default="telegram-toolkit-mcp", description="Service name for tracing"
    )
    service_version: str = Field(default="1.0.0", description="Service version for tracing")
    trace_sampling_rate: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Trace sampling rate (0.0-1.0)"
    )
    trace_max_attributes: int = Field(
        default=128, ge=1, le=1000, description="Maximum number of attributes per span"
    )
    trace_max_events: int = Field(
        default=128, ge=1, le=1000, description="Maximum number of events per span"
    )

    model_config = {"frozen": True}


class AppConfig(BaseModel):
    """Complete application configuration."""

    telegram: TelegramConfig
    server: ServerConfig
    performance: PerformanceConfig
    resources: ResourceConfig
    observability: ObservabilityConfig
    debug: bool = Field(default=False, description="Enable debug mode")

    model_config = {"frozen": True}


def load_config() -> AppConfig:
    """
    Load configuration from environment variables.

    Returns:
        AppConfig: Validated application configuration

    Raises:
        ValidationError: If configuration is invalid
    """
    try:
        # Load environment variables from .env file
        try:
            from dotenv import load_dotenv

            load_dotenv()
        except ImportError:
            # dotenv not available, rely on system environment
            pass
        # Load Telegram configuration
        telegram_config = TelegramConfig(
            api_id=int(os.getenv("TELEGRAM_API_ID", "0")),
            api_hash=os.getenv("TELEGRAM_API_HASH", ""),
            session_string=os.getenv("TELEGRAM_STRING_SESSION"),
        )

        # Load other configurations
        config = AppConfig(
            telegram=telegram_config,
            server=ServerConfig(
                host=os.getenv("MCP_SERVER_HOST", "localhost"),
                port=int(os.getenv("MCP_SERVER_PORT", "8000")),
                log_level=os.getenv("MCP_SERVER_LOG_LEVEL", "INFO"),
            ),
            performance=PerformanceConfig(
                flood_sleep_threshold=int(os.getenv("FLOOD_SLEEP_THRESHOLD", "60")),
                request_timeout=int(os.getenv("REQUEST_TIMEOUT", "30")),
                max_page_size=int(os.getenv("MAX_PAGE_SIZE", "100")),
            ),
            resources=ResourceConfig(
                temp_dir=os.getenv("TEMP_DIR", "/tmp/mcp-resources"),
                resource_max_age_hours=int(os.getenv("RESOURCE_MAX_AGE_HOURS", "24")),
                ndjson_chunk_size=int(os.getenv("NDJSON_CHUNK_SIZE", "1000")),
            ),
            observability=ObservabilityConfig(
                enable_prometheus_metrics=os.getenv("ENABLE_PROMETHEUS_METRICS", "true").lower()
                == "true",
                enable_opentelemetry_tracing=os.getenv(
                    "ENABLE_OPENTELEMETRY_TRACING", "true"
                ).lower()
                == "true",
                otlp_endpoint=os.getenv("OTLP_ENDPOINT"),
            ),
            debug=os.getenv("DEBUG", "false").lower() == "true",
        )

        return config

    except ValidationError as e:
        raise ValueError(f"Configuration validation failed: {e}") from e
    except ValueError as e:
        raise ValueError(f"Configuration loading failed: {e}") from e


def validate_telegram_credentials(config: AppConfig) -> bool:
    """
    Validate Telegram API credentials.

    Args:
        config: Application configuration

    Returns:
        bool: True if credentials are valid
    """
    telegram = config.telegram

    # Debug logging
    print(
        f"DEBUG: Validating credentials - api_id: {telegram.api_id}, api_hash_len: {len(telegram.api_hash) if telegram.api_hash else 0}"
    )

    if not telegram.api_id or not telegram.api_hash:
        print("DEBUG: Missing api_id or api_hash")
        return False

    # Basic validation - API ID should be a reasonable number
    try:
        api_id_int = int(telegram.api_id)
        print(f"DEBUG: API ID int value: {api_id_int}")
        # Telegram API IDs can be larger than 999999
        if api_id_int <= 0:
            print(f"DEBUG: API ID invalid: {api_id_int}")
            return False
    except (ValueError, TypeError) as e:
        print(f"DEBUG: API ID conversion error: {e}")
        return False

    # API hash should be 32-character hex string
    if len(telegram.api_hash) != 32:
        print(f"DEBUG: API hash length invalid: {len(telegram.api_hash)}")
        return False

    print("DEBUG: Credentials validation passed")
    return True


# Global configuration instance
_config: AppConfig | None = None


def get_config() -> AppConfig:
    """Get global configuration instance."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reset_config() -> None:
    """Reset global configuration (for testing)."""
    global _config
    _config = None
