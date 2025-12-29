"""
FastAPI Dependencies for Keycloak Authentication

Provides:
- Token extraction from Authorization header
- Token validation dependency
- Role-based authorization dependencies
"""
import logging
from typing import Optional, List, Dict, Any

from fastapi import Depends, HTTPException, status, Request

from app.core.keycloak import KeycloakConfig, extract_roles, get_username

logger = logging.getLogger(__name__)


async def get_token_from_header(request: Request) -> Optional[str]:
    """Extract Bearer token from Authorization header"""
    auth_header = request.headers.get("Authorization")
    
    if not auth_header:
        return None
    
    if not auth_header.startswith("Bearer "):
        return None
    
    return auth_header[7:]


async def get_current_user(
    request: Request,
    token: Optional[str] = Depends(get_token_from_header)
) -> Dict[str, Any]:
    """
    Validate token and return user claims
    
    Raises:
        HTTPException 401 if token is missing or invalid
    """
    if not token:
        logger.warning(f"Missing authorization token for {request.url.path}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Try to validate with each realm's validator
    validators = KeycloakConfig.get_validators()
    
    for realm, validator in validators.items():
        claims = await validator.validate(token)
        if claims:
            username = get_username(claims)
            logger.info(f"Authenticated user: {username} from realm: {realm}")
            return {"claims": claims, "realm": realm, "username": username}
    
    logger.warning(f"Token validation failed for all realms")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def require_roles(
    required_roles: List[str],
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Verify user has at least one of the required roles
    
    Args:
        required_roles: List of roles (any one is sufficient)
        user: Current user from get_current_user dependency
        
    Returns:
        User dict if authorized
        
    Raises:
        HTTPException 403 if user lacks required roles
    """
    user_roles = extract_roles(user["claims"])
    
    # Check if user has any of the required roles
    if not any(role in user_roles for role in required_roles):
        username = user.get("username")
        logger.warning(
            f"User {username} denied access: requires one of {required_roles}, "
            f"has {user_roles}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions. Required role(s): {', '.join(required_roles)}",
        )
    
    return user


def create_role_dependency(roles: List[str]):
    """
    Factory to create role-checking dependencies
    
    Usage:
        admin_required = create_role_dependency(["ADMIN"])
        
        @app.get("/admin-route")
        async def admin_route(user = Depends(admin_required)):
            ...
    """
    async def check_roles(
        user: Dict[str, Any] = Depends(get_current_user)
    ) -> Dict[str, Any]:
        return await require_roles(roles, user)
    
    return check_roles
