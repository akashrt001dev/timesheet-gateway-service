"""
Simple Keycloak Authentication Routes

Redirects users to Keycloak for login/logout without token management in gateway.
The backend services handle authentication and authorization.
"""
import logging
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, status, Request
from fastapi.responses import RedirectResponse, JSONResponse

from app.core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])

# Create a separate router for OAuth2 callback (no /auth prefix)
oauth2_router = APIRouter(tags=["OAuth2"])

# Create a separate router for logout (no /auth prefix for /logout endpoint)
logout_router = APIRouter(tags=["Authentication"])


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


@router.api_route("/logout", methods=["GET", "PUT", "POST"], name="Keycloak Logout")
async def logout(request: Request):
    """
    Redirect user to Keycloak logout page (OIDC RP-Initiated Logout).
    
    Extracts id_token from cookies and builds logout request with:
    - id_token_hint: The ID token for token hint
    - client_id: The Keycloak client ID
    - post_logout_redirect_uri: Where to redirect after logout
    
    Supports GET, PUT, and POST methods.
    
    Returns:
        202 Accepted with JSON response containing redirectURL
        (matches Java Spring Gateway response format)
    """
    settings = get_settings()
    
    if not settings.keycloak_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OAuth2 is not enabled"
        )
    
    # Build Keycloak logout URL
    logout_endpoint = f"{settings.keycloak_server_url}/realms/{settings.keycloak_realm}/protocol/openid-connect/logout"
    
    # Build query params manually to avoid encoding post_logout_redirect_uri
    query_params = []
    
    # Get access_token from cookies for id_token_hint
    token = request.cookies.get("access_token", "")
    if token:
        query_params.append(f"id_token_hint={token}")
    
    query_params.append(f"client_id={settings.keycloak_client_id}")
    query_params.append(f"post_logout_redirect_uri={settings.post_logout_redirect_uri}")
    
    logout_url = f"{logout_endpoint}?{'&'.join(query_params)}"
    logger.info(f"Redirecting to Keycloak logout: {logout_endpoint}")
    logger.info(f"Post-logout redirect URI: {settings.post_logout_redirect_uri}")
    
    # Return 202 Accepted with JSON body containing redirectURL (matches Java Gateway)
    response = JSONResponse(
        status_code=202,
        content={"redirectURL": logout_url}
    )
    response.headers["Location"] = logout_url
    return response


# Logout route without /auth prefix (accessible at /logout)
@logout_router.api_route("/logout", methods=["GET", "PUT", "POST"], name="Logout")
async def logout_no_prefix(request: Request):
    """
    Logout endpoint - matches Java Gateway behavior (RP-Initiated Logout).
    
    This is accessible at /logout (without /auth prefix).
    Supports GET, PUT, and POST methods.
    
    Extracts access_token from cookies and builds logout request with:
    - id_token_hint: The access token for token hint
    - client_id: The Keycloak client ID
    - post_logout_redirect_uri: Where to redirect after logout
    
    Returns:
        202 Accepted with JSON response containing redirectURL
        (matches Java Spring Gateway response format)
    """
    settings = get_settings()
    
    if not settings.keycloak_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OAuth2 is not enabled"
        )
    
    # Build Keycloak logout URL
    logout_endpoint = f"{settings.keycloak_server_url}/realms/{settings.keycloak_realm}/protocol/openid-connect/logout"
    
    # Build query params manually to avoid encoding post_logout_redirect_uri
    query_params = []
    
    # Get access_token from cookies for id_token_hint
    token = request.cookies.get("access_token", "")
    if token:
        query_params.append(f"id_token_hint={token}")
    
    query_params.append(f"client_id={settings.keycloak_client_id}")
    query_params.append(f"post_logout_redirect_uri={settings.post_logout_redirect_uri}")
    
    logout_url = f"{logout_endpoint}?{'&'.join(query_params)}"
    logger.info(f"Logging out user and redirecting to: {logout_url}")
    logger.info(f"Post-logout redirect URI: {settings.post_logout_redirect_uri}")
    
    # Return 202 Accepted with JSON body containing redirectURL (matches Java Gateway)
    response = JSONResponse(
        status_code=202,
        content={"redirectURL": logout_url}
    )
    response.headers["Location"] = logout_url
    return response


@oauth2_router.get("/login/oauth2/code/{provider_or_realm}", name="OAuth2 Callback")
async def oauth2_callback(request: Request, provider_or_realm: str):
    """
    OAuth2 callback endpoint that receives authorization code from Keycloak.
    
    This endpoint is called by Keycloak after user login with authorization code.
    It exchanges the authorization code for tokens directly (no forwarding).
    
    Keycloak Flow:
    1. User clicks login → Redirected to Keycloak
    2. User authenticates with Keycloak
    3. Keycloak redirects back to this endpoint with authorization code
    4. Gateway exchanges code for tokens (using Keycloak token endpoint)
    5. Gateway returns tokens to client or redirects to home
    
    Query Parameters (provided by Keycloak):
        code: Authorization code to exchange for tokens
        state: State parameter for CSRF protection
        session_state: Keycloak session state
    
    Args:
        request: FastAPI request with query parameters (code, state, session_state)
        provider_or_realm: Provider name or realm name (e.g., 'smmc-io-prod')
    
    Returns:
        Redirect to home page with tokens in secure HTTP-only cookies
    """
    settings = get_settings()
    
    logger.info(f"OAuth2 callback received for provider/realm: {provider_or_realm}")
    logger.debug(f"Query params: {dict(request.query_params)}")
    
    try:
        # Get authorization code from query parameters
        code = request.query_params.get("code")
        state = request.query_params.get("state")
        
        if not code:
            logger.error("OAuth2 callback: Missing authorization code")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing authorization code",
            )
        
        logger.info(f"OAuth2 code received, exchanging for tokens...")
        logger.info(f"  Authorization code: {code[:30]}..." if len(code) > 30 else f"  Authorization code: {code}")
        logger.info(f"  State: {state}")
        
        # Exchange authorization code for tokens
        # POST to Keycloak token endpoint
        token_endpoint = (
            f"{settings.keycloak_server_url}/realms/{settings.keycloak_realm}"
            f"/protocol/openid-connect/token"
        )
        
        token_request_data = {
            "grant_type": "authorization_code",
            "client_id": settings.keycloak_client_id,
            "client_secret": settings.keycloak_client_secret,
            "code": code,
            "redirect_uri": settings.keycloak_redirect_uri,
        }
        
        logger.info(f"Token request details:")
        logger.info(f"  Endpoint: {token_endpoint}")
        logger.info(f"  Client ID: {settings.keycloak_client_id}")
        logger.info(f"  Client Secret: {'*' * len(settings.keycloak_client_secret)}")
        logger.info(f"  Redirect URI: {settings.keycloak_redirect_uri}")
        logger.info(f"  Grant Type: authorization_code")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            token_response = await client.post(
                token_endpoint,
                data=token_request_data,
            )
        
        if token_response.status_code != 200:
            logger.error(
                f"Token exchange failed: {token_response.status_code}"
            )
            logger.error(f"Keycloak response: {token_response.text}")
            logger.error(f"This typically means:")
            logger.error(f"  1. Authorization code has expired (check timestamp)")
            logger.error(f"  2. Authorization code already used (each code can only be used once)")
            logger.error(f"  3. Redirect URI mismatch (must match exactly)")
            logger.error(f"  4. Client credentials mismatch (client_id or client_secret)")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token exchange failed: {token_response.json().get('error_description', token_response.text)}",
            )
        
        tokens = token_response.json()
        logger.info(f"Token exchange successful, user authenticated")
        
        # Create response that redirects to home page
        response = RedirectResponse(
            url=settings.post_login_redirect_path,
            status_code=302
        )
        
        # Store tokens in secure HTTP-only cookies
        # access_token: short-lived, used for API requests
        # refresh_token: long-lived, used to get new access tokens
        if "access_token" in tokens:
            response.set_cookie(
                key="access_token",
                value=tokens["access_token"],
                httponly=True,
                secure=True,  # HTTPS only
                samesite="lax",  # CSRF protection
                max_age=tokens.get("expires_in", 3600),  # Token TTL
            )
            logger.info(f"Access token set in cookie (TTL: {tokens.get('expires_in')} seconds)")
        
        if "refresh_token" in tokens:
            response.set_cookie(
                key="refresh_token",
                value=tokens["refresh_token"],
                httponly=True,
                secure=True,
                samesite="lax",
                max_age=tokens.get("refresh_expires_in", 86400 * 30),  # 30 days
            )
            logger.info("Refresh token set in cookie")
        
        logger.info(f"Redirecting to: {settings.post_login_redirect_path}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error processing OAuth2 callback: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OAuth2 callback processing failed",
        )