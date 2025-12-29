"""
Gateway Security Configuration Module

IMPORTANT: This gateway does NOT validate JWT tokens.
Token validation is handled by backend services.

This module only:
1. Defines PUBLIC_ROUTES (routes that don't require authentication at gateway)
2. Implements TokenRelay (forward Authorization headers as-is)
3. Preserves all incoming headers for backend services

Spring Cloud Gateway Equivalent:
- permit_all routes (no auth enforcement at gateway level)
- default-filters: [TokenRelay=] (forward all headers)
- Backend services handle actual token validation
"""
import logging

logger = logging.getLogger(__name__)


# Public routes from Spring application.yml permit_all configuration
# The gateway does NOT validate tokens for these routes.
# They are still proxied to backends, which may enforce auth.
PUBLIC_ROUTES = {
    "/login",                              # Login endpoint
    "/oauth2",                             # OAuth2 endpoints  
    "/app",                                # React frontend
    "/home",                               # Flutter frontend
    "/v3/api-docs",                        # OpenAPI docs
    "/user-management-service/user/ssoid",  # SSO ID endpoint
    "/entity-service/entityID",            # Entity ID lookup
    "/entity-service/entity/logo",         # Entity logo
    "/entity-service/entity/allEntity",    # All entities
}


def is_public_route(path: str) -> bool:
    """
    Check if a path is public (no auth required at gateway level).
    
    Note: Paths can still be protected by backend services.
    The gateway simply forwards all requests; it doesn't validate tokens.
    
    Args:
        path: Request path
        
    Returns:
        True if route is public, False otherwise
    """
    # Check exact match or prefix match
    return any(path.startswith(route) for route in PUBLIC_ROUTES)
