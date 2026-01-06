"""
CORS Middleware for FastAPI Gateway

Handles:
1. CORS preflight (OPTIONS) requests without proxying to backends
2. CORS response headers for cross-origin requests
3. OAuth2/Keycloak token relay with proper headers
4. Forwarded headers for reverse proxy (Nginx/HAProxy)
5. Request origin validation

This middleware works with Spring Cloud Gateway WebFlux CORS configuration equivalent.
"""
import logging
from typing import Callable, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse

from app.core.cors import (
    get_cors_config,
    build_cors_headers,
    is_cors_request,
    get_allowed_origin,
    should_proxy_options,
)

logger = logging.getLogger(__name__)


class CORSPreflightMiddleware(BaseHTTPMiddleware):
    """
    CORS Preflight Middleware - Handles OPTIONS requests without proxying to backends.
    
    This middleware must be placed AFTER the global CORSMiddleware in the middleware stack.
    
    Problem it solves:
    - Browser sends OPTIONS preflight to Keycloak OAuth2 endpoints
    - Keycloak returns 405 (Method Not Allowed)
    - Browser blocks the actual request due to CORS error
    
    Solution:
    - Intercept OPTIONS requests early
    - Check if backend supports OPTIONS (usually doesn't for Keycloak)
    - Return 200 OK with proper CORS headers instead of proxying
    """
    
    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        """
        Intercept requests and handle CORS preflight.
        
        Args:
            request: Incoming HTTP request
            call_next: Next middleware in chain
            
        Returns:
            Response (either preflight response or proxied response)
        """
        path = request.url.path
        method = request.method
        
        # Only handle OPTIONS requests (CORS preflight)
        if method != "OPTIONS":
            return await call_next(request)
        
        # Check if this is a CORS request (has Origin header)
        request_origin = request.headers.get("Origin")
        if not is_cors_request(request_origin):
            logger.debug(f"OPTIONS request without Origin header: {path}")
            return await call_next(request)
        
        # Check if OPTIONS should be proxied to backend
        # (most backends don't support OPTIONS, especially Keycloak)
        if not should_proxy_options(path):
            logger.debug(f"Handling CORS preflight locally: {method} {path} from {request_origin}")
            
            # Get CORS config
            cors_config = get_cors_config()
            
            # Get allowed origin (validate against configured origins)
            allowed_origin = get_allowed_origin(request_origin, cors_config.origins)
            
            if not allowed_origin:
                logger.warning(
                    f"CORS preflight rejected for disallowed origin: {request_origin} for path {path}"
                )
                # Return 403 Forbidden for disallowed origins
                return StarletteResponse(
                    status_code=403,
                    headers={
                        "Content-Type": "text/plain",
                    },
                )
            
            logger.debug(f"CORS preflight allowed for origin: {allowed_origin}")
            
            # Build CORS response headers
            cors_headers = build_cors_headers(allow_origin=allowed_origin)
            
            # Add request-specific headers (from the preflight request)
            request_method = request.headers.get("Access-Control-Request-Method")
            request_headers = request.headers.get("Access-Control-Request-Headers")
            
            if request_method:
                cors_headers["Access-Control-Request-Method"] = request_method
            if request_headers:
                cors_headers["Access-Control-Request-Headers"] = request_headers
            
            # Return 200 OK preflight response
            return StarletteResponse(
                status_code=200,
                headers=cors_headers,
            )
        
        # Proxy OPTIONS request to backend (rare case)
        logger.debug(f"Proxying OPTIONS request: {path}")
        return await call_next(request)


class CORSResponseMiddleware(BaseHTTPMiddleware):
    """
    Add CORS response headers to all responses.
    
    This complements the global CORSMiddleware to ensure:
    1. CORS headers are present on all responses (not just CORS requests)
    2. Proper credential handling for OAuth2 flows
    3. Consistent CORS policy across all endpoints
    """
    
    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        """
        Add CORS headers to response.
        
        Args:
            request: Incoming request
            call_next: Next middleware
            
        Returns:
            Response with CORS headers
        """
        path = request.url.path
        
        # Get the response from downstream
        response = await call_next(request)
        
        # Check if this is a CORS request
        request_origin = request.headers.get("Origin")
        if not is_cors_request(request_origin):
            # Not a CORS request, skip adding CORS headers
            return response
        
        # Get CORS configuration
        cors_config = get_cors_config()
        
        # Get allowed origin
        allowed_origin = get_allowed_origin(request_origin, cors_config.origins)
        if not allowed_origin:
            # Origin not allowed, skip CORS headers
            logger.debug(f"CORS headers not added for disallowed origin: {request_origin}")
            return response
        
        # Add CORS headers if not already present
        cors_headers = build_cors_headers(allow_origin=allowed_origin)
        for header_name, header_value in cors_headers.items():
            if header_name.lower() not in {k.lower() for k in response.headers.keys()}:
                response.headers[header_name] = header_value
        
        logger.debug(
            f"CORS headers added for {request.method} {path} from {allowed_origin}"
        )
        
        return response


class AuthorizationHeaderMiddleware(BaseHTTPMiddleware):
    """
    Token Relay Middleware - Handles Authorization header for OAuth2 flows.
    
    Ensures:
    1. Authorization header is properly forwarded to backend services
    2. Bearer tokens from cookies are converted to Authorization header
    3. Keycloak token is properly relayed
    """
    
    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        """
        Process Authorization header.
        
        Args:
            request: Incoming request
            call_next: Next middleware
            
        Returns:
        Response from downstream
        """
        path = request.url.path
        
        # Skip OAuth2 callback endpoints (they have special handling)
        if path.startswith("/login/oauth2/code"):
            return await call_next(request)
        
        # Check for Authorization header
        auth_header = request.headers.get("Authorization")
        
        # If no Authorization header but access_token cookie exists, create Authorization header
        if not auth_header and "access_token" in request.cookies:
            access_token = request.cookies.get("access_token")
            if access_token:
                # Add Authorization header from cookie
                request.headers._list.append(
                    (b"authorization", f"Bearer {access_token}".encode())
                )
                logger.debug(f"Added Authorization header from access_token cookie for {path}")
        
        return await call_next(request)


class ForwardedHeadersMiddleware(BaseHTTPMiddleware):
    """
    Forwarded Headers Middleware - Essential for reverse proxy setup (Nginx/HAProxy).
    
    Ensures backend services get correct:
    1. Original client IP (X-Forwarded-For)
    2. Original protocol (X-Forwarded-Proto) - http vs https
    3. Original host (X-Forwarded-Host)
    4. Original port (X-Forwarded-Port)
    
    This is critical when gateway is behind Nginx/HAProxy with HTTPS termination.
    Without this, backend services think all requests are HTTP from Nginx IP.
    """
    
    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        """
        Add or preserve forwarded headers.
        
        Args:
            request: Incoming request
            call_next: Next middleware
            
        Returns:
            Response from downstream
        """
        path = request.url.path
        
        # Preserve existing forwarded headers if already present (from proxy chain)
        # Otherwise, create them based on the request
        
        # X-Forwarded-For: Original client IP
        if "X-Forwarded-For" not in request.headers:
            if request.client:
                request.headers._list.append(
                    (b"x-forwarded-for", request.client.host.encode())
                )
                logger.debug(f"Added X-Forwarded-For: {request.client.host} for {path}")
        
        # X-Forwarded-Proto: Original protocol (http or https)
        if "X-Forwarded-Proto" not in request.headers:
            proto = request.url.scheme
            request.headers._list.append(
                (b"x-forwarded-proto", proto.encode())
            )
            logger.debug(f"Added X-Forwarded-Proto: {proto} for {path}")
        
        # X-Forwarded-Host: Original host from Host header
        if "X-Forwarded-Host" not in request.headers:
            host = request.headers.get("Host")
            if host:
                request.headers._list.append(
                    (b"x-forwarded-host", host.encode())
                )
                logger.debug(f"Added X-Forwarded-Host: {host} for {path}")
        
        return await call_next(request)
