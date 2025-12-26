"""
FastAPI Main Application
Gateway Service Entry Point
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
        title="Gateway REST API",
        description="Gateway API REST calls using FastAPI",
        version="1.0",
        lifespan=lifespan,
    )

    # Configure logging
    configure_logging(settings.log_level)

    # Add middleware (order matters - first added = last executed)
    # 1. CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_credentials,
        allow_methods=settings.cors_methods,
        allow_headers=settings.cors_headers,
    )

    # 2. Header removal middleware
    app.add_middleware(HeaderRemovalMiddleware)

    # 3. Request logging middleware
    app.add_middleware(RequestLoggingMiddleware)

    # 4. Correlation ID middleware
    app.add_middleware(CorrelationIDMiddleware)

    # 5. Authentication middleware
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

    # Include gateway routing (primary purpose of the gateway)
    app.include_router(gateway_routes.router)

    # Create minimal OpenAPI schema - gateway should be transparent
    app.openapi_schema = None
    app.openapi = lambda: None

    app_instance = app
    logger.info(f"Application created: {settings.app_name}")
    logger.info(f"Listening on {settings.server_host}:{settings.server_port}")
    logger.info("Gateway is ready to route requests to backend services")

    return app


# Create application instance
app = create_app()


def main():
    """
    Main entry point
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
