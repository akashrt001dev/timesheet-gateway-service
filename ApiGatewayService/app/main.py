"""
FastAPI API Gateway - Production-Ready Reverse Proxy
Main application entry point for the API Gateway service.

This gateway acts as a reverse proxy for multiple backend services,
routing requests based on path prefixes and forwarding all HTTP methods.
Frontend is served from an external source.

Features:
- Multi-service routing with path-based forwarding
- All HTTP methods (GET, POST, PUT, PATCH, DELETE, OPTIONS)
- Request/response header forwarding
- Query parameter preservation
- Request body forwarding
- Redirect following
- Comprehensive error handling
- Health check endpoint
"""
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, status, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
import uvicorn

from app.core.config import get_settings, configure_logging
from app.core.logging import setup_logging
from app.filters.middleware import (
    AuthenticationMiddleware,
    CorrelationIDMiddleware,
    RequestLoggingMiddleware,
    CORSMiddleware as CustomCORSMiddleware,
    HeaderRemovalMiddleware,
)
from app.api import gateway_routes

logger = logging.getLogger(__name__)

# Global application instance
app_instance: Optional[FastAPI] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager
    Handles startup and shutdown events
    """
    # Startup
    settings = get_settings()
    setup_logging(log_level=settings.log_level)
    logger.info(f"Starting {settings.app_name} on {settings.server_host}:{settings.server_port}")

    yield

    # Shutdown
    logger.info(f"Shutting down {settings.app_name}")


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application

    Returns:
        Configured FastAPI application instance
    """
    global app_instance

    settings = get_settings()

    # Create application
    app = FastAPI(
        title="API Gateway",
        description="Reverse proxy gateway for backend services",
        version="1.0.0",
        lifespan=lifespan,
        docs_url=None,  # Disable Swagger UI for production
        redoc_url=None,  # Disable ReDoc for production
        openapi_url=None,  # Disable OpenAPI schema for production
    )

    # Configure logging
    configure_logging(settings.log_level)

    # Add middleware (order matters - first added = last executed in request flow)
    # 1. CORS middleware - handle cross-origin requests
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_credentials,
        allow_methods=settings.cors_methods,
        allow_headers=settings.cors_headers,
    )

    # 2. Header removal middleware - remove sensitive headers
    app.add_middleware(HeaderRemovalMiddleware)

    # 3. Request logging middleware - log all requests
    app.add_middleware(RequestLoggingMiddleware)

    # 4. Correlation ID middleware - add request correlation IDs
    app.add_middleware(CorrelationIDMiddleware)

    # 5. Authentication middleware - validate JWT tokens
    app.add_middleware(AuthenticationMiddleware)

    # Exception handlers
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """Handle HTTP exceptions"""
        logger.error(
            f"HTTP Exception: {exc.status_code} - {exc.detail}",
            extra={"correlation_id": request.scope.get("correlation_id", "N/A")},
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.detail,
                "status_code": exc.status_code,
                "correlation_id": request.scope.get("correlation_id", "N/A"),
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle general exceptions"""
        logger.exception(
            f"Unhandled exception: {str(exc)}",
            extra={"correlation_id": request.scope.get("correlation_id", "N/A")},
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "Internal server error",
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "correlation_id": request.scope.get("correlation_id", "N/A"),
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

    # Include gateway routing (core purpose of this gateway)
    app.include_router(gateway_routes.router)

    app_instance = app
    logger.info(f"Application created: {settings.app_name}")
    logger.info(f"Listening on {settings.server_host}:{settings.server_port}")
    logger.info("Gateway routes initialized - ready to proxy requests")

    return app


# Create application instance
app = create_app()


def main():
    """
    Main entry point for the FastAPI application
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