"""
Simple Keycloak Authentication Routes

Redirects users to Keycloak for login/logout without token management in gateway.
The backend services handle authentication and authorization.
"""
import logging
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import RedirectResponse

from app.core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get("/login", name="Keycloak Login")
async def login():
    """
    Redirect user to Keycloak login page (OIDC Authorization Code Flow)
    """
    settings = get_settings()

    if not settings.keycloak_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OAuth2 is not enabled"
        )

    auth_endpoint = (
        f"{settings.keycloak_server_url}/realms/"
        f"{settings.keycloak_realm}/protocol/openid-connect/auth"
    )

    params = {
        "response_type": "code",
        "client_id": settings.keycloak_client_id,
        "redirect_uri": settings.keycloak_redirect_uri,
        "scope": "openid profile email offline_access roles",
        # ❌ grant_type REMOVED (IMPORTANT)
    }

    login_url = f"{auth_endpoint}?{urlencode(params)}"

    logger.info(f"Redirecting to Keycloak login")

    return RedirectResponse(url=login_url, status_code=302)


@router.get("/logout", name="Keycloak Logout")
async def logout():
    """
    Redirect user to Keycloak logout page.
    
    After logout, user is redirected to the post-logout redirect path.
    """
    settings = get_settings()
    
    if not settings.keycloak_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OAuth2 is not enabled"
        )
    
    # Build Keycloak logout URL
    logout_endpoint = f"{settings.keycloak_server_url}/realms/{settings.keycloak_realm}/protocol/openid-connect/logout"
    
    params = {
        "redirect_uri": settings.post_logout_redirect_path,
    }
    
    logout_url = f"{logout_endpoint}?{urlencode(params)}"
    logger.info(f"Redirecting to Keycloak logout: {logout_endpoint}")
    
    return RedirectResponse(url=logout_url, status_code=302)
