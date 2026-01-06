"""
Production-Ready CORS Configuration for OAuth2/Keycloak Gateway

Handles:
- CORS preflight (OPTIONS) requests
- OAuth2/Keycloak authentication flow
- Token relay with proper headers
- Forwarded headers for reverse proxy (Nginx)
- Token refresh without breaking CORS

Key Issues Fixed:
1. OPTIONS requests to Keycloak endpoints no longer proxied (return 200 locally)
2. Proper CORS headers for cross-origin OAuth2 requests
3. Credentials support for session-based authentication
4. Preflight caching to reduce latency
5. Multiple origin support for dev/staging/prod
"""
from typing import List, Optional
from pydantic import BaseModel


class CORSConfig(BaseModel):
    """
    CORS Configuration for FastAPI Gateway.
    
    This replaces Spring's HttpSecurity().cors() configuration.
    """
    
    # Origins allowed to make cross-origin requests
    # Include Keycloak server if it's on a different domain
    origins: List[str] = [
        "http://localhost:3000",         # Local React dev
        "http://localhost:8080",         # Local Flutter dev
        "https://app.timesmartai.ca",    # Production React/Flutter frontend
        "https://idm.timesmart.io",      # Keycloak server (OAuth2 provider)
    ]
    
    # Methods allowed in cross-origin requests
    methods: List[str] = [
        "GET",
        "POST",
        "PUT",
        "DELETE",
        "PATCH",
        "OPTIONS",  # CORS preflight
        "HEAD",
    ]
    
    # Headers clients can send in cross-origin requests
    allow_headers: List[str] = [
        # Standard headers
        "Content-Type",
        "Accept",
        "Origin",
        "Accept-Encoding",
        "User-Agent",
        "Referer",
        
        # Authentication headers
        "Authorization",          # Bearer tokens
        "Cookie",                 # Session cookies
        "X-CSRF-Token",          # CSRF protection
        
        # Custom headers
        "X-Requested-With",      # XHR indicator
        "X-Correlation-ID",      # Request tracing
        "X-tenantID",            # Multi-tenancy
        "X-User-ID",             # User identification
        "X-API-Key",             # API authentication
        
        # CORS headers (some CORS implementations echo back)
        "Access-Control-Allow-Origin",
        "Access-Control-Allow-Methods",
        "Access-Control-Allow-Headers",
        "Access-Control-Allow-Credentials",
    ]
    
    # Headers to expose in cross-origin responses
    # Browser will allow JavaScript to access these headers
    expose_headers: List[str] = [
        "Content-Type",
        "Content-Length",
        "Authorization",
        "Set-Cookie",           # Important for session-based auth
        "X-Correlation-ID",     # Tracing
        "X-RateLimit-Limit",    # Rate limiting info
        "X-RateLimit-Remaining",
        "X-RateLimit-Reset",
    ]
    
    # Allow credentials (cookies, authorization headers, TLS client certificates)
    # REQUIRED for OAuth2 with Keycloak when using cookies for session storage
    allow_credentials: bool = True
    
    # Cache preflight responses for 24 hours
    # Browsers will not send OPTIONS preflight again within this time
    max_age: int = 86400  # 24 hours in seconds
    
    # Add CORS headers to all responses (not just CORS requests)
    # Required for proper CORS handling
    expose_to_all: bool = True


def get_cors_config(origins: Optional[List[str]] = None) -> CORSConfig:
    """
    Get CORS configuration with optional origin override.
    
    Args:
        origins: Optional custom origins list to override defaults
        
    Returns:
        CORSConfig instance
    """
    config = CORSConfig()
    if origins:
        config.origins = origins
    return config


# OAuth2/Keycloak-specific routes that should NOT be proxied
# These endpoints handle preflight requests locally without proxying to Keycloak
OAUTH2_ENDPOINTS = {
    "/login",                       # Local login redirect to Keycloak
    "/oauth2",                      # OAuth2 callback handling
    "/login/oauth2/code",           # OAuth2 authorization code callback
    "/logout",                      # Local logout handler
    "/auth/logout",                 # Alternative logout endpoint
    "/auth/login",                  # Local auth login
}

# Keycloak server endpoints that should handle OPTIONS locally
# (Not proxied to Keycloak server)
KEYCLOAK_AUTH_PATHS = {
    "/realms/",                     # Keycloak realm endpoints
    "/auth/realms/",                # Legacy Keycloak path
}

# Preflight request paths that should return 200 OK without proxying
# These are typically OPTIONS requests to protected endpoints that would otherwise
# be proxied to backends that don't support OPTIONS
PREFLIGHT_ALLOWED_PATHS = {
    # Keycloak OAuth2 endpoints
    "/realms/",
    "/auth/realms/",
    "/protocol/openid-connect/",
    
    # User-facing API endpoints (backend services will handle actual requests)
    "/auth/",
    "/user/",
    "/roles/",
    "/contracts/",
    "/entity/",
    "/entityID/",
    "/timesheet/",
    "/activity/",
    "/emailtemplate/",
    "/ticket/",
    "/feedback/",
}


def should_proxy_options(path: str) -> bool:
    """
    Determine if an OPTIONS request should be proxied to backend.
    
    Some backends might support OPTIONS for CORS preflight.
    Most don't, especially Keycloak OAuth2 endpoints.
    
    Args:
        path: Request path
        
    Returns:
        True if request should be proxied, False if handled locally
    """
    # Never proxy OPTIONS to Keycloak OAuth2 endpoints
    if any(path.startswith(oauth_path) for oauth_path in OAUTH2_ENDPOINTS):
        return False
    
    # Never proxy OPTIONS to Keycloak authentication paths
    if any(path.startswith(kc_path) for kc_path in KEYCLOAK_AUTH_PATHS):
        return False
    
    # By default, handle OPTIONS locally (return 200 OK)
    return False


def build_cors_headers(allow_origin: str = "*") -> dict:
    """
    Build CORS response headers for preflight and regular responses.
    
    Args:
        allow_origin: Specific origin to allow (or "*" for any origin)
        
    Returns:
        Dictionary of CORS headers
    """
    config = get_cors_config()
    
    return {
        "Access-Control-Allow-Origin": allow_origin,
        "Access-Control-Allow-Methods": ", ".join(config.methods),
        "Access-Control-Allow-Headers": ", ".join(config.allow_headers),
        "Access-Control-Expose-Headers": ", ".join(config.expose_headers),
        "Access-Control-Allow-Credentials": "true" if config.allow_credentials else "false",
        "Access-Control-Max-Age": str(config.max_age),
        
        # Browser security headers
        "Vary": "Origin",  # Tell caches to vary by Origin header
    }


def is_cors_request(request_origin: Optional[str]) -> bool:
    """
    Check if request is a CORS request (has Origin header).
    
    Args:
        request_origin: Origin header value from request
        
    Returns:
        True if Origin header is present (CORS request)
    """
    return request_origin is not None and request_origin.strip() != ""


def get_allowed_origin(request_origin: Optional[str], allowed_origins: List[str]) -> Optional[str]:
    """
    Get allowed origin for CORS response header.
    
    For security, we should never respond with Access-Control-Allow-Origin: *
    if credentials are allowed (allow_credentials=true).
    
    Args:
        request_origin: Origin header from request
        allowed_origins: List of allowed origins
        
    Returns:
        Specific origin to allow, or None if origin is not allowed
    """
    if not request_origin:
        return None
    
    # Wildcard origin allows any origin (only use if credentials are NOT allowed)
    if "*" in allowed_origins:
        return request_origin  # Echo back the requesting origin
    
    # Check if origin is in allowed list
    if request_origin in allowed_origins:
        return request_origin
    
    # Origin not allowed
    return None
