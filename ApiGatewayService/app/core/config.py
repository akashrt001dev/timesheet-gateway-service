"""
FastAPI Gateway Configuration Module
Converts Spring Boot application.yml to Pydantic Settings
"""
import logging
from typing import List, Optional
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field


class GatewayRouteConfig:
    """Gateway Route Configuration"""

    ROUTES = {
        "user-management-service": {
            "id": "user-management-service",
            "uri": "lb://user-management-service",
            "predicates": ["/auth/**", "/user/**", "/roles/**"],
            "rewrites": {
                "/auth/(?P<path>.*)": "/$path",
                "/user/(?P<path>.*)": "/$path",
                "/roles/(?P<path>.*)": "/$path",
            },
            "remove_headers": ["Cookie", "Set-Cookie"],
        },
        "contract-management-service": {
            "id": "contract-management-service",
            "uri": "lb://contract-management-service",
            "predicates": ["/contracts/**"],
            "rewrites": {
                "/contracts/(?P<path>.*)": "/$path",
            },
            "remove_headers": ["Cookie", "Set-Cookie"],
        },
        "entity-service": {
            "id": "entity-service",
            "uri": "lb://entity-service",
            "predicates": ["/entity/**"],
            "rewrites": {
                "/entity/(?P<path>.*)": "/$path",
            },
            "remove_headers": ["Cookie", "Set-Cookie"],
        },
        "timesheet-management-service": {
            "id": "timesheet-management-service",
            "uri": "lb://timesheet-management-service",
            "predicates": ["/timesheet/**", "/activity/**"],
            "rewrites": {
                "/timesheet/(?P<path>.*)": "/$path",
                "/activity/(?P<path>.*)": "/$path",
            },
            "remove_headers": ["Cookie", "Set-Cookie"],
        },
    }


class Settings(BaseSettings):
    """Application Settings from environment variables"""

    # Server Configuration
    server_port: int = Field(default=8000, alias="SERVER_PORT")
    server_host: str = Field(default="0.0.0.0", alias="SERVER_HOST")
    environment: str = Field(default="local", alias="ENVIRONMENT")
    app_name: str = "gateway-service"

    # JWT Configuration
    jwt_secret: str = Field(
        default="BvPHGM8C0ia4uOuxxqPD5DTbWC9F9TWvPStp3pb7ARo0oK2mJ3pd3YG4lxA9i8bj6OTbadwezxgeEByY",
        alias="JWT_SECRET",
    )
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")

    # Eureka Configuration
    eureka_enabled: bool = Field(default=True, alias="EUREKA_ENABLED")
    eureka_server_url: str = Field(
        default="http://localhost:8761/eureka/", alias="EUREKA_SERVER_URL"
    )
    eureka_app_name: str = Field(default="gateway-service", alias="EUREKA_APP_NAME")

    # Upstream Services Configuration
    user_service_url: Optional[str] = Field(
        default="http://localhost:8001", alias="USER_SERVICE_URL"
    )
    contract_service_url: Optional[str] = Field(
        default="http://localhost:8002", alias="CONTRACT_SERVICE_URL"
    )
    entity_service_url: Optional[str] = Field(
        default="http://localhost:8003", alias="ENTITY_SERVICE_URL"
    )
    timesheet_service_url: Optional[str] = Field(
        default="http://localhost:8004", alias="TIMESHEET_SERVICE_URL"
    )

    # Logging Configuration
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # CORS Configuration
    cors_origins: List[str] = Field(default=["*"], alias="CORS_ORIGINS")
    cors_credentials: bool = Field(default=True, alias="CORS_CREDENTIALS")
    cors_methods: List[str] = Field(
        default=["GET", "POST", "PUT", "DELETE", "OPTIONS"], alias="CORS_METHODS"
    )
    cors_headers: List[str] = Field(default=["*"], alias="CORS_HEADERS")

    # Actuator Configuration
    actuator_enabled: bool = Field(default=True, alias="ACTUATOR_ENABLED")

    # Request Timeout
    request_timeout_seconds: int = Field(default=30, alias="REQUEST_TIMEOUT_SECONDS")

    # Zipkin/Distributed Tracing
    zipkin_enabled: bool = Field(default=False, alias="ZIPKIN_ENABLED")
    zipkin_url: Optional[str] = Field(
        default="http://localhost:9411/api/v2/spans", alias="ZIPKIN_URL"
    )

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get settings singleton instance"""
    return Settings()


# Export gateway routes
GATEWAY_ROUTES = GatewayRouteConfig.ROUTES

# Logging configuration
def configure_logging(log_level: str = "INFO"):
    """Configure logging for the application"""
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    # Suppress noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
