"""
FastAPI API Gateway - Spring Cloud Gateway Equivalent

Production-ready reverse proxy gateway for backend services.
Implements the routing, rewriting, and security behavior from 
Java Spring Cloud Gateway application.yml.

KEY FEATURES:
- Frontend routing to React/Flutter UIs (no token validation)
- Backend service routing with automatic path rewriting
- TokenRelay: Forward all headers including Authorization
- OAuth2/Keycloak integration with proper CORS handling
- CORS preflight (OPTIONS) handled locally without proxying to backends
- All HTTP methods supported
- Request correlation IDs for tracing

RUNS WITH ONE COMMAND:
    uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.core.config import get_settings, configure_logging
from app.core.cors import get_cors_config
from app.filters.cors_middleware import (
    CORSPreflightMiddleware,
    CORSResponseMiddleware,
    AuthorizationHeaderMiddleware,
    ForwardedHeadersMiddleware,
)
from app.api import gateway_routes
from app.api import auth_routes

logger = logging.getLogger(__name__)

# Global app instance
app_instance: Optional[FastAPI] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    settings = get_settings()
    configure_logging(settings.log_level)
    logger.info(
        f"Starting {settings.app_name} on {settings.server_host}:{settings.server_port}"
    )
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"React URI: {settings.react_uri}")
    logger.info(f"Flutter URI: {settings.flutter_uri}")
    
    if settings.keycloak_enabled:
        logger.info(f"Keycloak Login: {settings.keycloak_server_url}/realms/{settings.keycloak_realm}/protocol/openid-connect/auth")
        logger.info(f"Keycloak Realm: {settings.keycloak_realm}")
        logger.info(f"CORS: Keycloak server ({settings.keycloak_server_url}) added to allowed origins")
    
    yield
    
    # Shutdown
    logger.info(f"Shutting down {settings.app_name}")


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.
    
    Middleware stack (order matters):
    1. CORSPreflightMiddleware - Handle OPTIONS locally (must be early)
    2. ForwardedHeadersMiddleware - Add forwarded headers for reverse proxy
    3. AuthorizationHeaderMiddleware - Token relay from cookies to Authorization header
    4. CORSResponseMiddleware - Add CORS headers to all responses
    5. Global CORSMiddleware - FastAPI built-in CORS handling
    6. Business logic (routes)
    
    Returns:
        Configured FastAPI application instance
    """
    global app_instance
    
    settings = get_settings()
    cors_config = get_cors_config()
    
    # Create application
    app = FastAPI(
        title="API Gateway",
        description="Spring Cloud Gateway equivalent - reverse proxy for backend services",
        version="1.0.0",
        lifespan=lifespan,
        docs_url=None,      # Disable Swagger UI in production
        redoc_url=None,     # Disable ReDoc in production
        openapi_url=None,   # Disable OpenAPI schema in production
    )
    
    # Configure logging
    configure_logging(settings.log_level)
    
    # Add custom middleware stack (order matters)
    # These must be added BEFORE the global CORSMiddleware
    
    # 1. Forwarded headers middleware (for reverse proxy support)
    app.add_middleware(ForwardedHeadersMiddleware)
    logger.info("Registered ForwardedHeadersMiddleware for reverse proxy headers (X-Forwarded-*)")
    
    # 2. CORS response headers middleware
    app.add_middleware(CORSResponseMiddleware)
    logger.info("Registered CORSResponseMiddleware to add CORS headers to responses")
    
    # 3. Authorization header middleware (token relay)
    app.add_middleware(AuthorizationHeaderMiddleware)
    logger.info("Registered AuthorizationHeaderMiddleware for token relay")
    
    # 4. CORS preflight middleware (handles OPTIONS without proxying)
    app.add_middleware(CORSPreflightMiddleware)
    logger.info("Registered CORSPreflightMiddleware for OPTIONS preflight handling")
    
    # 5. Global CORS middleware (must be after custom middleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_config.origins,
        allow_credentials=cors_config.allow_credentials,
        allow_methods=cors_config.methods,
        allow_headers=cors_config.allow_headers,
        expose_headers=cors_config.expose_headers,
        max_age=cors_config.max_age,
    )
    logger.info(f"Registered CORSMiddleware with {len(cors_config.origins)} allowed origins")
    logger.info(f"CORS allowed origins: {', '.join(cors_config.origins)}")
    logger.info(f"CORS credentials: {cors_config.allow_credentials}")
    logger.info(f"CORS max_age: {cors_config.max_age}s (preflight cache)")
    
    # Exception handlers
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """Handle HTTP exceptions"""
        logger.error(
            f"HTTP {exc.status_code}: {exc.detail}",
            extra={"path": request.url.path}
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.detail,
                "status_code": exc.status_code,
                "path": request.url.path,
            },
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle unhandled exceptions"""
        logger.exception(f"Unhandled exception: {str(exc)}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "status_code": 500,
                "path": request.url.path,
            },
        )
    
    # Health check endpoint (required for monitoring and Kubernetes probes)
    @app.get("/health", tags=["Gateway"])
    async def health_check():
        """Gateway health check endpoint"""
        return {
            "status": "healthy",
            "service": settings.app_name,
            "version": "1.0.0",
        }
    
    # Include authentication routes (Keycloak redirects) - MUST be before gateway catch-all
    if settings.keycloak_enabled:
        app.include_router(auth_routes.router)
        app.include_router(auth_routes.oauth2_router)
        app.include_router(auth_routes.logout_router)
        logger.info("Authentication routes registered (/auth/login, /auth/logout, /logout, /login/oauth2/code/*)")
    
    # Include gateway routing (catch-all) - LAST, as fallback for all other routes
    app.include_router(gateway_routes.router)
    
    app_instance = app
    logger.info(f"Application created: {settings.app_name}")
    logger.info(f"Gateway routes initialized")
    
    return app


# Create application instance
app = create_app()


def main():
    """
    Main entry point for the FastAPI application.
    
    Starts the Uvicorn server with configured host and port.
    To run: uvicorn app.main:app --host 0.0.0.0 --port 8000
    """
    settings = get_settings()
    
    uvicorn.run(
        "app.main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=settings.environment == "local",
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
