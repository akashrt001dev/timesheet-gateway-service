"""
FastAPI Middleware - Equivalent to Spring Boot Gateway Filters
Converts Spring Cloud Gateway filters to FastAPI middleware
"""
import logging
import time
import json
from typing import Callable, Optional
from uuid import uuid4
import httpx
from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.datastructures import Headers
from starlette.responses import StreamingResponse, JSONResponse
from app.core.security import RouterValidator, get_jwt_util
from app.core.logging import generate_correlation_id

logger = logging.getLogger(__name__)


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """
    Authentication Middleware - Equivalent to Spring Boot AuthenticationFilter
    Validates JWT tokens and extracts claims for downstream services
    """

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        """
        Process request through authentication filter

        Args:
            request: Incoming request
            call_next: Next middleware/handler

        Returns:
            Response with populated user headers if authenticated
        """
        path = request.url.path

        # Check if route requires authentication
        if not RouterValidator.is_secured(path):
            logger.debug(f"Open endpoint accessed: {path}")
            return await call_next(request)

        # Check if Authorization header is present
        if RouterValidator.is_auth_missing(request):
            logger.warning(f"Authorization header missing for {path}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Authorization header is missing in request"},
            )

        # Extract and validate token
        token = RouterValidator.get_auth_header(request)
        if not token:
            logger.warning(f"Invalid Authorization header format for {path}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Authorization header is invalid"},
            )

        # Validate JWT token
        jwt_util = get_jwt_util()
        try:
            claims = jwt_util.validate_token(token)
            logger.info(f"Token validated for user: {claims.get('id', 'unknown')}")

            # Add user claims to request scope for downstream handlers
            request.scope["user_claims"] = claims

            # Populate headers from claims
            user_headers = RouterValidator.populate_request_with_headers(claims)
            for header_key, header_value in user_headers.items():
                request.headers = Headers(
                    {**request.headers, header_key: header_value}
                )

        except HTTPException as e:
            return JSONResponse(
                status_code=e.status_code,
                content={"detail": e.detail},
            )
        except Exception as e:
            logger.error(f"Token validation error: {str(e)}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Unauthorized"},
            )

        return await call_next(request)


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """
    Correlation ID Middleware - Adds unique ID to each request for tracing
    """

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        """
        Add correlation ID to request and response

        Args:
            request: Incoming request
            call_next: Next middleware/handler

        Returns:
            Response with correlation ID header
        """
        # Get or generate correlation ID
        correlation_id = request.headers.get(
            "X-Correlation-ID", generate_correlation_id()
        )

        # Add to request scope
        request.scope["correlation_id"] = correlation_id

        # Add to logger
        request.scope["logger"] = logger

        # Process request
        response = await call_next(request)

        # Add correlation ID to response
        response.headers["X-Correlation-ID"] = correlation_id

        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Request/Response Logging Middleware
    Logs all incoming requests and outgoing responses
    """

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        """
        Log request and response details

        Args:
            request: Incoming request
            call_next: Next middleware/handler

        Returns:
            Response with logging
        """
        request_id = str(uuid4())
        correlation_id = request.scope.get("correlation_id", "N/A")
        start_time = time.time()

        # Log incoming request
        logger.info(
            f"[{request_id}] {request.method} {request.url.path} | "
            f"Correlation-ID: {correlation_id}"
        )

        try:
            response = await call_next(request)
        except HTTPException as exc:
            duration = time.time() - start_time
            logger.warning(
                f"[{request_id}] Request failed with status {exc.status_code} | "
                f"Duration: {duration:.3f}s"
            )
            raise

        # Log response
        duration = time.time() - start_time
        logger.info(
            f"[{request_id}] {request.method} {request.url.path} | "
            f"Status: {response.status_code} | Duration: {duration:.3f}s"
        )

        return response


class CORSMiddleware(BaseHTTPMiddleware):
    """
    CORS Middleware - Equivalent to Spring Boot CorsConfig
    Handles Cross-Origin Resource Sharing
    """

    def __init__(self, app, allow_origins: list = None):
        """
        Initialize CORS middleware

        Args:
            app: FastAPI application
            allow_origins: List of allowed origins (default: ["*"])
        """
        super().__init__(app)
        self.allow_origins = allow_origins or ["*"]

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        """
        Handle CORS headers

        Args:
            request: Incoming request
            call_next: Next middleware/handler

        Returns:
            Response with CORS headers
        """
        # Handle preflight requests
        if request.method == "OPTIONS":
            return Response(
                status_code=200,
                headers={
                    "Access-Control-Allow-Origin": ", ".join(self.allow_origins)
                    if self.allow_origins != ["*"]
                    else "*",
                    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                    "Access-Control-Allow-Headers": "*",
                    "Access-Control-Max-Age": "3600",
                },
            )

        response = await call_next(request)

        # Add CORS headers to response
        response.headers["Access-Control-Allow-Origin"] = (
            ", ".join(self.allow_origins)
            if self.allow_origins != ["*"]
            else "*"
        )
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = (
            "GET, POST, PUT, DELETE, OPTIONS"
        )
        response.headers["Access-Control-Allow-Headers"] = "*"

        return response


class HeaderRemovalMiddleware(BaseHTTPMiddleware):
    """
    Header Removal Middleware - Removes sensitive headers before forwarding
    Equivalent to Spring Gateway RemoveRequestHeader filter
    """

    HEADERS_TO_REMOVE = {"cookie", "set-cookie"}

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        """
        Remove sensitive headers from request and response

        Args:
            request: Incoming request
            call_next: Next middleware/handler

        Returns:
            Response without sensitive headers
        """
        # Filter request headers (create new Headers without sensitive ones)
        filtered_headers = {
            name: value
            for name, value in request.headers.items()
            if name.lower() not in self.HEADERS_TO_REMOVE
        }
        request.headers = Headers(filtered_headers)

        response = await call_next(request)

        # Remove headers from response
        headers_to_remove = []
        for header in self.HEADERS_TO_REMOVE:
            if header in response.headers:
                headers_to_remove.append(header)

        for header in headers_to_remove:
            del response.headers[header]

        return response
