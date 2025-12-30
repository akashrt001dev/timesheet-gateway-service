"""
FastAPI Gateway Router - Spring Cloud Gateway Equivalent

This module implements routing and proxying matching the Java Spring Cloud Gateway
configuration from application.yml with Keycloak OAuth2 JWT token validation.

FRONTEND ROUTING (Public - no auth required):
  /app/**  → react-uri
  /home/** → flutter-uri

PUBLIC ROUTES (No auth required):
  /login, /oauth2, /, /home, /app, /docs, /health, /actuator/health
  /user-management-service/user/ssoid/**
  /entity-service/entityID
  /entity-service/entity/logo
  /entity-service/entity/allEntity

BACKEND SERVICE ROUTING (Protected - JWT required):
  /auth/**, /user/**, /roles/**      → user-management-service (path rewritten)
  /contracts/**                       → contract-management-service (path rewritten)
  /entity/**, /entityID/**           → entity-service (path rewritten)
  /timesheet/**, /activity/**        → timesheet-management-service (path rewritten)
  /emailtemplate/**                  → notification-service (path rewritten)

SECURITY:
  - Validates JWT tokens from Keycloak (supports multiple realms)
  - Returns 401 for missing/invalid tokens on protected routes
  - Forwards Authorization header to backend services (TokenRelay)
  - Extracts and logs user info from JWT claims

All HTTP methods supported: GET, POST, PUT, DELETE, PATCH, OPTIONS, HEAD
"""
import logging
import re
from typing import Dict, Optional, Tuple
from urllib.parse import urljoin

import httpx
from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import StreamingResponse, RedirectResponse

from app.core.config import get_settings
from app.core.keycloak import KeycloakConfig, extract_roles, get_username

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

# Public routes (no authentication required)
PUBLIC_ROUTES = {
    "/login",
    "/oauth2",
    "/login/oauth2",  # OAuth2 callback endpoint and all OAuth2 callback paths
    "/",
    "/app",
    "/docs",
    "/health",
    "/actuator/health",
    "/user-management-service/user/ssoid",
    "/entity-service/entityID",
    "/entity-service/entity/logo",
    "/entity-service/entity/allEntity",
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
            # "/": settings.flutter_uri,   # Spring: Path=/home/**
        }
        
        # Backend service routes with path rewriting rules
        # Each entry maps a URL prefix to (service_url, prefix_to_strip)
        # 
        # Spring RewritePath behavior:
        #   /auth/(?<path>.*)  → /${path}   (strip /auth)
        #   /user/(?<path>.*)  → /${path}   (strip /user)
        #   /roles/(?<path>.*) → /${path}   (strip /roles)
        self.backend_routes = {
            # OAuth2 callback endpoint - forward to user management service
            "/login/oauth2": (
                settings.user_management_service_url,
                "/login/oauth2"
            ),
            # Service-specific prefixes (longest first for priority matching)
            "/user-management-service": (
                settings.user_management_service_url,
                "/user-management-service"
            ),
            "/contract-management-service": (
                settings.contract_management_service_url,
                "/contract-management-service"
            ),
            "/entity-service": (
                settings.entity_service_url,
                "/entity-service"
            ),
            "/timesheet-management-service": (
                settings.timesheet_management_service_url,
                "/timesheet-management-service"
            ),
            "/notification-service": (
                settings.notification_service_url,
                "/notification-service"
            ),
            # Direct API prefixes (backward compatibility)
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
        
        # Add CORS headers to all proxied responses (required for cross-origin requests)
        # This prevents ORB (Object Restriction Blocking) errors in the browser
        settings = get_settings()
        cors_origin = settings.cors_origins[0] if settings.cors_origins else "*"
        
        # Only add if not already present (upstream headers take precedence)
        if "access-control-allow-origin" not in {k.lower() for k in response_headers.keys()}:
            response_headers["Access-Control-Allow-Origin"] = cors_origin
        if "access-control-allow-credentials" not in {k.lower() for k in response_headers.keys()}:
            response_headers["Access-Control-Allow-Credentials"] = "true" if settings.cors_credentials else "false"
        if "access-control-allow-methods" not in {k.lower() for k in response_headers.keys()}:
            response_headers["Access-Control-Allow-Methods"] = ", ".join(settings.cors_methods)
        if "access-control-allow-headers" not in {k.lower() for k in response_headers.keys()}:
            response_headers["Access-Control-Allow-Headers"] = ", ".join(settings.cors_headers)
        
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


def _is_public_route(path: str) -> bool:
    """Check if path is public (no auth required)"""
    # Exact match
    if path in PUBLIC_ROUTES:
        return True
    
    # Prefix match
    for public in PUBLIC_ROUTES:
        if path.startswith(public + "/"):
            return True
    
    return False


async def _validate_token_if_required(request: Request, path: str) -> Optional[Dict]:
    """
    Validate JWT token for protected routes
    
    Returns:
        User claims dict if authenticated, None if public route
        
    Raises:
        HTTPException with redirect to Keycloak login if token is missing on protected route
        HTTPException 401 if token is invalid
    """
    from urllib.parse import urlencode
    import secrets
    
    settings = get_settings()
    
    # Public routes don't need auth
    if _is_public_route(path):
        return None
    
    # Skip auth if Keycloak is disabled
    if not settings.keycloak_enabled:
        logger.warning(f"Keycloak disabled but accessing protected route: {path}")
        return None
    
    # Extract token from Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        logger.warning(f"Missing authorization token for {path}, redirecting to Keycloak login")
        
        # Redirect to Keycloak login
        keycloak_server = settings.keycloak_server_url.rstrip("/")
        realm = settings.keycloak_realm
        client_id = settings.keycloak_client_id
        redirect_uri = settings.keycloak_redirect_uri
        
        # Build authorization request parameters
        auth_params = {
            "response_type": "code",
            "client_id": client_id,
            "scope": "openid profile email offline_access roles",
            "redirect_uri": redirect_uri,
            "state": secrets.token_urlsafe(32),
            "nonce": secrets.token_urlsafe(32),
        }
        
        keycloak_auth_url = (
            f"{keycloak_server}/realms/{realm}/protocol/openid-connect/auth"
            f"?{urlencode(auth_params)}"
        )
        
        logger.info(f"Redirecting to Keycloak: {keycloak_auth_url}")
        return RedirectResponse(
            url=keycloak_auth_url, 
            status_code=307,  # Use 307 for temporary redirect (preserves POST method)
            headers={
                "Cache-Control": "no-store, no-cache",
                "Pragma": "no-cache",
            }
        )
    
    token = auth_header[7:]
    
    # Try to validate with each realm's validator
    validators = KeycloakConfig.get_validators()
    for realm, validator in validators.items():
        claims = await validator.validate(token)
        if claims:
            username = get_username(claims)
            roles = extract_roles(claims)
            logger.info(
                f"Authenticated user: {username} from realm: {realm} "
                f"with roles: {', '.join(roles)}"
            )
            return {"claims": claims, "realm": realm, "username": username, "roles": roles}
    
    logger.warning(f"Token validation failed for all realms for path: {path}")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
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
    Validates JWT tokens from Keycloak for protected routes and proxies to backend services.
    
    FRONTEND (Public):
      /app/**  → react-uri (no rewriting)
      /home/** → flutter-uri (no rewriting)
    
    BACKEND (Protected - JWT required):
      /auth/**, /user/**, /roles/**      → user-management-service (path rewritten)
      /contracts/**                       → contract-management-service (path rewritten)
      /entity/**, /entityID/**           → entity-service (path rewritten)
      /timesheet/**, /activity/**        → timesheet-management-service (path rewritten)
      /emailtemplate/**                  → notification-service (path rewritten)
    
    SECURITY:
      - Validates JWT tokens from Keycloak (supports multiple realms)
      - Returns 401 for missing/invalid tokens on protected routes
      - Public routes (/login, /oauth2, /, /home, /app, /docs) bypass auth
      - TokenRelay: Authorization header forwarded to backend
    
    Args:
        request: Incoming HTTP request
        path: Request path (path parameter)
        
    Returns:
        StreamingResponse with upstream service response
    """
    # Normalize path
    full_path = f"/{path}" if path else "/"
    
    # Handle CORS preflight requests (OPTIONS) - bypass authentication
    if request.method == "OPTIONS":
        logger.debug(f"CORS preflight request: {full_path}")
        return StreamingResponse(
            content=iter([]),
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, PATCH, OPTIONS, HEAD",
                "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With, Accept, Origin",
                "Access-Control-Max-Age": "3600",
            },
        )
    
    try:
        # Validate token for protected routes (may redirect to Keycloak login)
        auth_result = await _validate_token_if_required(request, full_path)
        
        # If redirect response (RedirectResponse), return it
        if isinstance(auth_result, RedirectResponse):
            return auth_result
        
        user = auth_result
        
        # Determine routing
        router_instance = GatewayRouter(get_settings())
        route_info = router_instance.determine_route(full_path)
        
        if not route_info:
            # Handle root path redirect to Flutter home
            if full_path == "/":
                # logger.info("Redirecting / to /home")
                # return RedirectResponse(url="/home", status_code=307)
                logger.info("Redirecting / to /")
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
