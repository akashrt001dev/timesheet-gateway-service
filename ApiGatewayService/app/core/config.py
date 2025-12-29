"""
FastAPI Gateway Configuration Module
Converts Spring Boot application.yml to Pydantic Settings

This gateway mirrors the Spring Cloud Gateway configuration:
- Frontend routing (/app, /home) to React and Flutter UIs
- Backend service routing with path rewriting
- Token relay (forward Authorization headers as-is)
- Keycloak OAuth2 JWT validation for protected endpoints
- Multi-realm support for different Keycloak realms
"""
import logging
import json
from typing import List, Optional, Union
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator, ConfigDict


class Settings(BaseSettings):
    """
    Application Settings from environment variables.
    
    Maps to Spring Cloud Gateway application.yml configuration:
    - Frontend URIs for React and Flutter apps
    - Backend service URLs (with domain-based routing, not IP:port)
    - CORS configuration
    - Server and timeout settings
    """

    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=False,
        validate_assignment=True,
    )

    # ========================================================================
    # SERVER CONFIGURATION
    # ========================================================================
    server_port: int = Field(default=8000, alias="SERVER_PORT")
    server_host: str = Field(default="0.0.0.0", alias="SERVER_HOST")
    environment: str = Field(default="local", alias="ENVIRONMENT")
    app_name: str = "api-gateway-service"
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # ========================================================================
    # FRONTEND CONFIGURATION (Spring Gateway: react-uri, flutter-uri)
    # ========================================================================
    react_uri: str = Field(
        default="https://app.timesmartai.ca",
        alias="REACT_URI",
        description="React frontend URI (Spring: react-uri)"
    )
    flutter_uri: str = Field(
        default="https://app.timesmartai.ca",
        alias="FLUTTER_URI",
        description="Flutter frontend URI (Spring: flutter-uri)"
    )

    # ========================================================================
    # BACKEND SERVICES CONFIGURATION (Domain-based URLs)
    # Spring Cloud Gateway uses: lb://service-name (load balanced)
    # Python implementation uses: direct URLs (can be service names in Docker/K8s)
    # ========================================================================
    user_management_service_url: str = Field(
        default="http://localhost:8001",
        alias="USER_MANAGEMENT_SERVICE_URL",
        description="User Management Service (auth, user, roles)"
    )
    contract_management_service_url: str = Field(
        default="http://localhost:8002",
        alias="CONTRACT_MANAGEMENT_SERVICE_URL",
        description="Contract Management Service"
    )
    entity_service_url: str = Field(
        default="http://localhost:8003",
        alias="ENTITY_SERVICE_URL",
        description="Entity Service"
    )
    timesheet_management_service_url: str = Field(
        default="http://localhost:8004",
        alias="TIMESHEET_MANAGEMENT_SERVICE_URL",
        description="Timesheet Management Service (timesheet, activity)"
    )
    notification_service_url: str = Field(
        default="http://localhost:8005",
        alias="NOTIFICATION_SERVICE_URL",
        description="Notification Service (emailtemplate)"
    )

    # ========================================================================
    # CORS CONFIGURATION
    # ========================================================================
    cors_origins: Union[str, List[str]] = Field(default="*", alias="CORS_ORIGINS")
    cors_credentials: bool = Field(default=True, alias="CORS_CREDENTIALS")
    cors_methods: Union[str, List[str]] = Field(
        default="GET,POST,PUT,DELETE,OPTIONS,PATCH,HEAD", alias="CORS_METHODS"
    )
    cors_headers: Union[str, List[str]] = Field(default="*", alias="CORS_HEADERS")

    # ========================================================================
    # ACTUATOR CONFIGURATION
    # ========================================================================
    actuator_enabled: bool = Field(default=True, alias="ACTUATOR_ENABLED")

    # ========================================================================
    # DISTRIBUTED TRACING CONFIGURATION (Optional)
    # ========================================================================
    zipkin_enabled: bool = Field(default=False, alias="ZIPKIN_ENABLED")
    zipkin_url: str = Field(default="http://localhost:9411/api/v2/spans", alias="ZIPKIN_URL")

    # ========================================================================
    # JWT CONFIGURATION
    # ========================================================================
    jwt_secret: str = Field(default="", alias="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")

    # ========================================================================
    # EUREKA SERVICE DISCOVERY CONFIGURATION
    # ========================================================================
    eureka_enabled: bool = Field(default=False, alias="EUREKA_ENABLED")
    eureka_server_url: str = Field(default="http://localhost:8761/eureka/", alias="EUREKA_SERVER_URL")
    eureka_app_name: str = Field(default="gateway-service", alias="EUREKA_APP_NAME")

    # ========================================================================
    # REQUEST CONFIGURATION
    # ========================================================================
    request_timeout_seconds: int = Field(default=30, alias="REQUEST_TIMEOUT_SECONDS")

    # ========================================================================
    # KEYCLOAK/OAUTH2 CONFIGURATION
    # ========================================================================
    keycloak_enabled: bool = Field(default=True, alias="KEYCLOAK_ENABLED")
    keycloak_server_url: str = Field(default="https://idm.timesmart.io", alias="KEYCLOAK_SERVER_URL")
    keycloak_realm: str = Field(default="smmc-uat-prod", alias="KEYCLOAK_REALM")
    keycloak_client_id: str = Field(default="spring-addons-confidential", alias="KEYCLOAK_CLIENT_ID")
    keycloak_client_secret: str = Field(default="", alias="KEYCLOAK_CLIENT_SECRET")
    keycloak_redirect_uri: str = Field(default="https://localhost/auth/callback", alias="KEYCLOAK_REDIRECT_URI")
    post_login_redirect_path: str = Field(default="/home/", alias="POST_LOGIN_REDIRECT_PATH")
    post_logout_redirect_path: str = Field(default="/home", alias="POST_LOGOUT_REDIRECT_PATH")

    # ========================================================================
    # VALIDATORS
    # ========================================================================
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
        if isinstance(v, list):
            return v
        if not isinstance(v, str):
            return [str(v)]
        v = v.strip()
        if v.startswith("["):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except (json.JSONDecodeError, ValueError):
                pass
        if "," in v:
            return [item.strip() for item in v.split(",") if item.strip()]
        if v:
            return [v]
        return []


@lru_cache()
def get_settings() -> Settings:
    """Get settings singleton instance"""
    try:
        return Settings()
    except Exception as e:
        print(f"ERROR loading settings: {e}")
        print("Make sure your .env file has the following variables:")
        print("  REACT_URI=https://app.timesmartai.ca")
        print("  FLUTTER_URI=https://app.timesmartai.ca")
        print("  USER_MANAGEMENT_SERVICE_URL=http://localhost:8001")
        print("  CONTRACT_MANAGEMENT_SERVICE_URL=http://localhost:8002")
        print("  ENTITY_SERVICE_URL=http://localhost:8003")
        print("  TIMESHEET_MANAGEMENT_SERVICE_URL=http://localhost:8004")
        print("  NOTIFICATION_SERVICE_URL=http://localhost:8005")
        raise


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
