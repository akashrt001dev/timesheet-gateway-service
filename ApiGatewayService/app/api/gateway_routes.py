"""
FastAPI Gateway Router - Spring Cloud Gateway Equivalent

This module implements routing and proxying matching the Java Spring Cloud Gateway
configuration from application.yml:

FRONTEND ROUTING:
  /app/**  → react-uri
  /home/** → flutter-uri

BACKEND SERVICE ROUTING WITH PATH REWRITING:
  /auth/**, /user/**, /roles/** 
    → user-management-service
    → strip prefix before forwarding

  /contracts/**
    → contract-management-service  
    → strip "/contracts"

  /entity/**, /entityID/**
    → entity-service
    → strip "/entity"

  /timesheet/**, /activity/**
    → timesheet-management-service
    → strip corresponding prefix

  /emailtemplate/**
    → notification-service
    → strip "/emailtemplate"

SECURITY:
  - NO token validation in gateway
  - Forward Authorization header as-is (TokenRelay)
  - All headers forwarded to backend services
  - Backend services handle authentication/authorization

All HTTP methods supported: GET, POST, PUT, DELETE, PATCH, OPTIONS, HEAD
"""
import logging
import re
from typing import Dict, Optional, Tuple
from urllib.parse import urljoin

import httpx
from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import StreamingResponse

from app.core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()

# HTTP client configuration for proxying
HTTPX_TIMEOUT = 30.0
HTTPX_CLIENT_CONFIG = {
    "timeout": HTTPX_TIMEOUT,
    "follow_redirects": True,
    "limits": httpx.Limits(max_keepalive_connections=100, max_connections=100),
}

# Hop-by-hop headers that should not be forwarded
HOP_BY_HOP_HEADERS = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host",
}


class GatewayRouter:
    """
    Routes requests to appropriate backends with Spring Cloud Gateway equivalent behavior.
    
    Implements exact routing and path rewriting logic from Java Gateway application.yml.
    """

    def __init__(self, settings):
        """
        Initialize gateway router with service URLs from settings.
        
        Args:
            settings: Application settings with service URLs
        """
        self.settings = settings
        
        # Frontend routes - no path rewriting
        # Spring: uri: ${react-uri}, uri: ${flutter-uri}
        self.frontend_routes = {
            "/app": settings.react_uri,      # Spring: Path=/app/**
            "/home": settings.flutter_uri,   # Spring: Path=/home/**
        }
        
        # Backend service routes with path rewriting rules
        # Each entry maps a URL prefix to (service_url, prefix_to_strip)
        # 
        # Spring RewritePath behavior:
        #   /auth/(?<path>.*)  → /${path}   (strip /auth)
        #   /user/(?<path>.*)  → /${path}   (strip /user)
        #   /roles/(?<path>.*) → /${path}   (strip /roles)
        self.backend_routes = {
            "/auth": (
                settings.user_management_service_url,
                "/auth"
            ),
            "/user": (
                settings.user_management_service_url,
                "/user"
            ),
            "/roles": (
                settings.user_management_service_url,
                "/roles"
            ),
            "/contracts": (
                settings.contract_management_service_url,
                "/contracts"
            ),
            "/entity": (
                settings.entity_service_url,
                "/entity"
            ),
            "/entityID": (
                settings.entity_service_url,
                "/entityID"
            ),
            "/timesheet": (
                settings.timesheet_management_service_url,
                "/timesheet"
            ),
            "/activity": (
                settings.timesheet_management_service_url,
                "/activity"
            ),
            "/emailtemplate": (
                settings.notification_service_url,
                "/emailtemplate"
            ),
        }

    def determine_route(self, path: str) -> Optional[Tuple[str, str]]:
        """
        Determine target URL and rewritten path for a given request path.
        
        Implements Spring Cloud Gateway predicate matching and RewritePath filters.
        
        Example transformations:
          /app/dashboard           → (react-uri, /app/dashboard)          [frontend, no rewrite]
          /auth/login              → (user-service, /login)                [rewritten]
          /contracts/123/download  → (contract-service, /123/download)    [rewritten]
          
        Args:
            path: Request path from incoming HTTP request
            
        Returns:
            Tuple of (target_url, rewritten_path) or None if no match
        """
        # Check frontend routes first (longer prefixes first)
        for prefix in sorted(self.frontend_routes.keys(), key=len, reverse=True):
            if path.startswith(prefix):
                target_url = self.frontend_routes[prefix]
                # Frontend: keep original path
                return target_url, path
        
        # Check backend routes (longer prefixes first to match most specific)
        for prefix in sorted(self.backend_routes.keys(), key=len, reverse=True):
            if path.startswith(prefix):
                service_url, strip_prefix = self.backend_routes[prefix]
                
                # Rewrite path: remove the prefix
                # Examples:
                #   /auth/login with /auth → /login
                #   /contracts/123 with /contracts → /123
                if path == prefix:
                    # Exact match: path becomes /
                    rewritten = "/"
                else:
                    # Remove prefix from path
                    rewritten = path[len(strip_prefix):]
                    # Ensure it starts with /
                    if not rewritten.startswith("/"):
                        rewritten = "/" + rewritten
                
                return service_url, rewritten
        
        # No matching route found
        return None


async def proxy_request(
    target_url: str,
    upstream_path: str,
    request: Request,
    timeout: float = HTTPX_TIMEOUT,
) -> Tuple[int, Dict[str, str], bytes]:
    """
    Proxy an HTTP request to a target upstream service.
    
    This function handles:
    - All HTTP methods (GET, POST, PUT, DELETE, PATCH, OPTIONS, HEAD)
    - Query parameters preservation
    - Request body forwarding
    - Header forwarding (excluding hop-by-hop headers)
    - Authorization header relay (TokenRelay)
    - Response handling
    
    Args:
        target_url: Base URL of target service (e.g., "http://localhost:8001")
        upstream_path: Path to forward (e.g., "/login")
        request: Incoming FastAPI request
        timeout: Request timeout in seconds
        
    Returns:
        Tuple of (status_code, headers_dict, response_body)
        
    Raises:
        HTTPException: On connection, timeout, or other proxying errors
    """
    # Build full target URL
    full_target_url = urljoin(target_url, upstream_path)
    if request.url.query:
        full_target_url = f"{full_target_url}?{request.url.query}"
    
    # Prepare headers: forward all except hop-by-hop headers
    # This implements TokenRelay - Authorization header is forwarded as-is
    forward_headers: Dict[str, str] = {}
    for header_name, header_value in request.headers.items():
        if header_name.lower() not in HOP_BY_HOP_HEADERS:
            forward_headers[header_name] = header_value
    
    # Add correlation ID if available (from middleware)
    if "correlation_id" in request.scope:
        forward_headers["X-Correlation-ID"] = request.scope["correlation_id"]
    
    # Read request body
    body = b""
    if request.method.upper() in {"POST", "PUT", "PATCH"}:
        body = await request.body()
    
    try:
        logger.info(
            f"Proxying {request.method} {request.url.path} → {full_target_url}",
            extra={"path": request.url.path, "method": request.method}
        )
        
        # Forward request to upstream service
        async with httpx.AsyncClient(**HTTPX_CLIENT_CONFIG) as client:
            response = await client.request(
                method=request.method.upper(),
                url=full_target_url,
                headers=forward_headers,
                content=body if body else None,
            )
        
        # Prepare response headers (exclude hop-by-hop)
        response_headers = {
            k: v for k, v in response.headers.items()
            if k.lower() not in HOP_BY_HOP_HEADERS
        }
        
        logger.debug(f"Upstream responded with {response.status_code}")
        return response.status_code, response_headers, response.content
    
    except httpx.TimeoutException:
        logger.error(f"Timeout proxying to {target_url}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Gateway timeout - upstream service did not respond",
        )
    except httpx.ConnectError:
        logger.error(f"Connection error to {target_url}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service unavailable - cannot reach upstream service",
        )
    except Exception as e:
        logger.exception(f"Error proxying to {target_url}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Bad gateway - error forwarding request",
        )


@router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
    tags=["Gateway"],
)
async def gateway_route(request: Request, path: str = ""):
    """
    Universal gateway route handler - Spring Cloud Gateway equivalent.
    
    This is the main entry point for all requests to the gateway.
    It implements the complete routing logic from the Java application.yml:
    
    FRONTEND:
      /app/**  → react-uri (no rewriting)
      /home/** → flutter-uri (no rewriting)
    
    BACKEND:
      /auth/**, /user/**, /roles/**      → user-management-service (path rewritten)
      /contracts/**                       → contract-management-service (path rewritten)
      /entity/**, /entityID/**           → entity-service (path rewritten)
      /timesheet/**, /activity/**        → timesheet-management-service (path rewritten)
      /emailtemplate/**                  → notification-service (path rewritten)
    
    SECURITY:
      - No token validation in gateway
      - All headers forwarded (Authorization header included)
      - Backend services handle authentication
    
    Args:
        request: Incoming HTTP request
        path: Request path (path parameter)
        
    Returns:
        StreamingResponse with upstream service response
    """
    # Normalize path
    full_path = f"/{path}" if path else "/"
    
    try:
        # Determine routing
        router_instance = GatewayRouter(get_settings())
        route_info = router_instance.determine_route(full_path)
        
        if not route_info:
            # Handle root path redirect to Flutter home
            if full_path == "/":
                from fastapi.responses import RedirectResponse
                logger.info("Redirecting / to /home")
                return RedirectResponse(url="/home", status_code=307)
            
            logger.warning(f"No route found for {full_path}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No route found for path: {full_path}",
            )
        
        target_url, rewritten_path = route_info
        
        logger.info(
            f"Route: {full_path} → {target_url}{rewritten_path}",
            extra={"path": full_path}
        )
        
        # Proxy request to target
        status_code, response_headers, response_body = await proxy_request(
            target_url=target_url,
            upstream_path=rewritten_path,
            request=request,
        )
        
        # Return response
        return StreamingResponse(
            iter([response_body]),
            status_code=status_code,
            headers=response_headers,
            media_type=response_headers.get("content-type", "application/octet-stream"),
        )
    
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Unexpected error: {str(exc)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
