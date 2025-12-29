"""
JWT Token Validation and Security Module
Converts Spring Boot JwtUtil and AuthenticationFilter to FastAPI
"""
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from functools import lru_cache
import jwt
from jwt import InvalidTokenError, DecodeError, ExpiredSignatureError
from fastapi import HTTPException, status, Request
from app.core.config import get_settings

logger = logging.getLogger(__name__)


class JwtUtil:
    """JWT Token Utility - Equivalent to Spring Boot JwtUtil"""

    def __init__(self, secret: str, algorithm: str = "HS256"):
        """
        Initialize JWT utility with secret key and algorithm

        Args:
            secret: Secret key for signing/verifying tokens
            algorithm: Algorithm to use (default: HS256)
        """
        self.secret = secret
        self.algorithm = algorithm

    def get_all_claims_from_token(self, token: str) -> Dict[str, Any]:
        """
        Extract all claims from JWT token

        Args:
            token: JWT token string

        Returns:
            Dictionary of claims

        Raises:
            HTTPException: If token is invalid or expired
        """
        try:
            payload = jwt.decode(token, self.secret, algorithms=[self.algorithm])
            return payload
        except ExpiredSignatureError:
            logger.warning("Token has expired")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
            )
        except (InvalidTokenError, DecodeError) as e:
            logger.warning(f"Invalid token: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )

    def is_token_expired(self, token: str) -> bool:
        """
        Check if token is expired

        Args:
            token: JWT token string

        Returns:
            True if expired, False otherwise
        """
        try:
            claims = self.get_all_claims_from_token(token)
            if "exp" not in claims:
                return False
            expiration_time = datetime.fromtimestamp(claims["exp"])
            return expiration_time < datetime.utcnow()
        except HTTPException:
            return True

    def is_invalid(self, token: str) -> bool:
        """
        Check if token is invalid (expired or malformed)

        Args:
            token: JWT token string

        Returns:
            True if invalid, False otherwise
        """
        return self.is_token_expired(token)

    def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validate token and return claims

        Args:
            token: JWT token string

        Returns:
            Dictionary of claims

        Raises:
            HTTPException: If token is invalid or expired
        """
        return self.get_all_claims_from_token(token)


@lru_cache()
def get_jwt_util() -> JwtUtil:
    """Get JWT utility singleton instance"""
    settings = get_settings()
    return JwtUtil(secret=settings.jwt_secret, algorithm=settings.jwt_algorithm)


class RouterValidator:
    """
    Route Validator - Equivalent to Spring Boot RouterValidator
    Determines which routes require authentication
    """

    OPEN_API_ENDPOINTS = {
        "/",
        "/health",
        "/auth/login",
        "/user/registerUserList",
        "/user/register",
        "/entityID",
        "/user/setpassword",
        "/user/updatepassword",
        "/user/forgetpassword",
        "/user",
        "/entity/logo",
        "/entity/logothumbnail",
        "/actuator/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/favicon.ico",
    }

    @classmethod
    def is_secured(cls, path: str) -> bool:
        """
        Check if a path requires authentication

        Args:
            path: Request path

        Returns:
            True if path requires auth, False if it's open
        """
        # Check if path exactly matches or starts with any open endpoint
        for endpoint in cls.OPEN_API_ENDPOINTS:
            if path == endpoint or path.startswith(endpoint.rstrip("*")):
                return False
        return True

    @classmethod
    def is_auth_missing(cls, request: Request) -> bool:
        """
        Check if Authorization header is missing

        Args:
            request: FastAPI Request object

        Returns:
            True if Authorization header is missing
        """
        return "authorization" not in request.headers

    @classmethod
    def get_auth_header(cls, request: Request) -> Optional[str]:
        """
        Extract token from Authorization header

        Args:
            request: FastAPI Request object

        Returns:
            Token string without "Bearer " prefix, or None
        """
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:]  # Remove "Bearer " prefix
        return auth_header

    @classmethod
    def populate_request_with_headers(cls, claims: Dict[str, Any]) -> Dict[str, str]:
        """
        Extract relevant headers from JWT claims for downstream services

        Args:
            claims: JWT claims dictionary

        Returns:
            Dictionary of headers to inject into request
        """
        headers = {}
        if "id" in claims:
            headers["X-User-ID"] = str(claims["id"])
        if "role" in claims:
            headers["X-User-Role"] = str(claims["role"])
        if "sub" in claims:
            headers["X-User-Subject"] = str(claims["sub"])
        return headers


def validate_jwt_token(token: str) -> Dict[str, Any]:
    """
    Validate JWT token and return claims

    Args:
        token: JWT token string

    Returns:
        Dictionary of claims

    Raises:
        HTTPException: If token is invalid
    """
    jwt_util = get_jwt_util()
    return jwt_util.validate_token(token)