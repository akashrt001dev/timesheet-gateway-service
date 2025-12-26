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
    
    """Gateway Route Configuration - Matches Spring Boot application.yml"""

    # Open endpoints from Spring security.client.permit-all
    OPEN_ENDPOINTS = {
        "/login/**",
        "/oauth2/**",
        "/",
        "/login-options",
        "/me",
        "/ui/**",
        "/app/**",
        "/v3/api-docs/**",
        "/user-management-service/user/ssoid/**",
        "/entity-service/entityID",
        "/entity-service/entity/logo",
        "/entity-service/entity/allEntity",
    }

    ROUTES = {
        "app": {
            "id": "app",
            "uri": "https://app.timesmartai.ca",
            "predicates": ["/app/**"],
            "rewrites": {},
            "remove_headers": [],
        },
        "home": {
            "id": "home",
            "uri": "https://app.timesmartai.ca",
            "predicates": ["/home/**"],
            "rewrites": {},
            "remove_headers": [],
        },
        "user-management-service": {
            "id": "user-management-service",
            "uri": "lb://user-management-service",
            "predicates": [
                "/auth/**",
                "/user/**",
                "/roles/**"
            ],
            "rewrites": {
                "/user-management-service/(?<path>.*)": "/${path}",
                "/auth/(?<path>.*)": "/${path}",
                "/user/(?<path>.*)": "/${path}",
                "/roles/(?<path>.*)": "/${path}",
            },
            "remove_headers": ["Cookie", "Set-Cookie"],
        },
        "contract-management-service": {
            "id": "contract-management-service",
            "uri": "lb://contract-management-service",
            "predicates": [
                "/contracts/**"
            ],
            "rewrites": {

                "/contracts/(?<path>.*)": "/${path}",
            },
            "remove_headers": ["Cookie", "Set-Cookie"],
        },
        "entity-service": {
            "id": "entity-service",
            "uri": "lb://entity-service",
            "predicates": [
                "/entity/**",
                "/entityID/**"
            ],
            "rewrites": {
                "/entity/(?<path>.*)"  : "/${path}",
                "/entityID/(?<path>.*)"  : "/${path}",
            },
            "remove_headers": ["Cookie", "Set-Cookie"],
        },
        "timesheet-management-service": {
            "id": "timesheet-management-service",
            "uri": "lb://timesheet-management-service",
            "predicates": [
                "/timesheet/**",
                "/activity/**"
            ],
            "rewrites": {

                "/timesheet/(?<path>.*)": "/${path}",
                "/activity/(?<path>.*)": "/${path}",
            },
            "remove_headers": ["Cookie", "Set-Cookie"],
        },
        "notification-service": {
            "id": "notification-service",
            "uri": "lb://notification-service",
            "predicates": [
                "/emailtemplate/**"
            ],
            "rewrites": {
                "/emailtemplate/(?<path>.*)": "/${path}",
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

    # Keycloak Configuration - From Spring OAuth2 providers
    keycloak_realms: List[str] = Field(
        default=[
            "smmc-uat-prod",
            "timesmart-master-uat",
            "tenethealth-uat-prod"
        ],
        alias="KEYCLOAK_REALMS"
    )
    keycloak_issuer_uris: List[str] = Field(
        default=[
            "https://idm.timesmart.io/realms/smmc-uat-prod",
            "https://idm.timesmart.io/realms/timesmart-master-uat",
            "https://idm.timesmart.io/realms/tenethealth-uat-prod"
        ],
        alias="KEYCLOAK_ISSUER_URIS"
    )
    keycloak_enabled: bool = Field(default=True, alias="KEYCLOAK_ENABLED")
    master_entity_name: str = Field(default="timesmart-master-uat", alias="MASTER_ENTITY_NAME")

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
    notification_service_url: Optional[str] = Field(
        default="http://localhost:8005", alias="NOTIFICATION_SERVICE_URL"
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