"""
FastAPI Gateway Configuration Module
Converts Spring Boot application.yml to Pydantic Settings
"""
import logging
import json
from typing import List, Optional, Union
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator, ConfigDict


class GatewayRouteConfig: 
    
    """Gateway Route Configuration"""

    ROUTES = {
        "user-management-service": {
            "id": "user-management-service",
            "uri": "lb://user-management-service",
            "predicates": [
                "/api/user-management-service/**",
                "/api/auth/**",
                "/api/user/**",
                "/api/roles/**"
            ],
            "rewrites": {
                "/api/user-management-service/(?<path>.*)": "/${path}",
                "/api/auth/(?<path>.*)": "/${path}",
                "/api/user/(?<path>.*)": "/${path}",
                "/api/roles/(?<path>.*)": "/${path}",
            },
            "remove_headers": ["Cookie", "Set-Cookie"],
        },
        "contract-management-service": {
            "id": "contract-management-service",
            "uri": "lb://contract-management-service",
            "predicates": [
                "/api/contract-managment-service/**",
                "/api/contract-management-service/**",
                "/api/contracts/**"
            ],
            "rewrites": {
                "/api/contract-managment-service/(?<path>.*)": "/${path}",
                "/api/contract-management-service/(?<path>.*)": "/${path}",
                "/api/contracts/(?<path>.*)": "/${path}",
            },
            "remove_headers": ["Cookie", "Set-Cookie"],
        },
        "entity-service": {
            "id": "entity-service",
            "uri": "lb://entity-service",
            "predicates": [
                "/api/entity-service/**",
                "/api/entity/**",
                "/api/app/entitySitePortal/**"
            ],
            "rewrites": {
                "/api/entity-service/(?<path>.*)": "/${path}",
                "/api/entity/(?<path>.*)": "/${path}",
                "/api/app/entitySitePortal/(?<path>.*)": "/entitySitePortal/${path}",
            },
            "remove_headers": ["Cookie", "Set-Cookie"],
        },
        "timesheet-management-service": {
            "id": "timesheet-management-service",
            "uri": "lb://timesheet-management-service",
            "predicates": [
                "/api/timesheet-management-service/**",
                "/api/timesheet/**",
                "/api/activity/**"
            ],
            "rewrites": {
                "/api/timesheet-management-service/(?<path>.*)": "/${path}",
                "/api/timesheet/(?<path>.*)": "/${path}",
                "/api/activity/(?<path>.*)": "/${path}",
            },
            "remove_headers": ["Cookie", "Set-Cookie"],
        },
    }


class Settings(BaseSettings):
    """Application Settings from environment variables"""

    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=False,
        validate_assignment=True,
    )

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
    cors_origins: Union[str, List[str]] = Field(default="*", alias="CORS_ORIGINS")
    cors_credentials: bool = Field(default=True, alias="CORS_CREDENTIALS")
    cors_methods: Union[str, List[str]] = Field(
        default="GET,POST,PUT,DELETE,OPTIONS", alias="CORS_METHODS"
    )
    cors_headers: Union[str, List[str]] = Field(default="*", alias="CORS_HEADERS")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins from various formats to list"""
        return cls._parse_list_field(v)

    @field_validator("cors_methods", mode="before")
    @classmethod
    def parse_cors_methods(cls, v):
        """Parse CORS methods from various formats to list"""
        return cls._parse_list_field(v)

    @field_validator("cors_headers", mode="before")
    @classmethod
    def parse_cors_headers(cls, v):
        """Parse CORS headers from various formats to list"""
        return cls._parse_list_field(v)

    @staticmethod
    def _parse_list_field(v):
        """Helper to parse list fields from various input formats"""
        # Already a list, return as-is
        if isinstance(v, list):
            return v
        
        # Convert to string for processing
        if not isinstance(v, str):
            return [str(v)]
        
        v = v.strip()
        
        # Try to parse as JSON array
        if v.startswith("["):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except (json.JSONDecodeError, ValueError):
                pass
        
        # Handle comma-separated values
        if "," in v:
            return [item.strip() for item in v.split(",") if item.strip()]
        
        # Single value (including "*")
        if v:
            return [v]
        
        # Empty/null - return default
        return []

    # Actuator Configuration
    actuator_enabled: bool = Field(default=True, alias="ACTUATOR_ENABLED")

    # Request Timeout
    request_timeout_seconds: int = Field(default=30, alias="REQUEST_TIMEOUT_SECONDS")

    # Zipkin/Distributed Tracing
    zipkin_enabled: bool = Field(default=False, alias="ZIPKIN_ENABLED")
    zipkin_url: Optional[str] = Field(
        default="http://localhost:9411/api/v2/spans", alias="ZIPKIN_URL"
    )


@lru_cache()
def get_settings() -> Settings:
    """Get settings singleton instance"""
    try:
        return Settings()
    except Exception as e:
        print(f"ERROR loading settings: {e}")
        print("Make sure your .env file has proper format for list fields:")
        print("  CORS_ORIGINS=*")
        print("  CORS_ORIGINS=http://localhost:3000,http://localhost:8000")
        print('  CORS_ORIGINS=["http://localhost:3000","http://localhost:8000"]')
        raise


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
