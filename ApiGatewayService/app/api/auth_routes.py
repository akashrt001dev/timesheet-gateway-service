"""
Simple Keycloak Authentication Routes

Redirects users to Keycloak for login/logout without token management in gateway.
The backend services handle authentication and authorization.
"""
import logging
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, status, Request
from fastapi.responses import RedirectResponse

from app.core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])

# Create a separate router for OAuth2 callback (no /auth prefix)
oauth2_router = APIRouter(tags=["OAuth2"])


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

@oauth2_router.get("/login/oauth2/code/{provider_or_realm}", name="OAuth2 Callback")
async def oauth2_callback(request: Request, provider_or_realm: str):
    """
    OAuth2 callback endpoint that receives authorization code from Keycloak.
    
    This endpoint is called by Keycloak after user login with authorization code.
    The authorization code is forwarded to the backend service for token exchange.
    
    Args:
        request: FastAPI request with query parameters (code, state, session_state)
        provider_or_realm: Provider name or realm name (e.g., 'smmc-io-prod')
    
    Returns:
        Response from backend service (typically redirects to home or sets tokens)
    """
    settings = get_settings()
    
    logger.info(f"OAuth2 callback received for provider/realm: {provider_or_realm}")
    logger.debug(f"Query params: {request.query_params}")
    
    # Forward the OAuth2 callback request to the user management service
    # The backend service will exchange the code for tokens
    try:
        from app.api.gateway_routes import proxy_request
        
        target_url = settings.user_management_service_url
        callback_path = f"/login/oauth2/code/{provider_or_realm}"
        
        status_code, response_headers, response_body = await proxy_request(
            target_url=target_url,
            upstream_path=callback_path,
            request=request,
        )
        
        logger.info(f"OAuth2 callback forwarded successfully, status: {status_code}")
        
        from fastapi.responses import StreamingResponse
        return StreamingResponse(
            iter([response_body]),
            status_code=status_code,
            headers=response_headers,
            media_type=response_headers.get("content-type", "application/octet-stream"),
        )
    except Exception as e:
        logger.exception(f"Error processing OAuth2 callback: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OAuth2 callback processing failed",
        )