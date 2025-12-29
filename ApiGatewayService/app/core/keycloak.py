"""
Keycloak Authentication Module

Handles:
- JWT token validation from multiple Keycloak realms
- Role extraction from realm and resource access
- Token caching and JWKS refresh
- Multi-realm support
"""
import logging
import json
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from functools import lru_cache

import jwt
import httpx

logger = logging.getLogger(__name__)

# Token cache
_token_cache: Dict[str, Dict[str, Any]] = {}
_jwks_cache: Dict[str, Any] = {}
_jwks_expiry: Dict[str, datetime] = {}


class KeycloakTokenValidator:
    """Validates JWT tokens from Keycloak"""
    
    def __init__(self, issuer_uri: str):
        """
        Initialize validator for a specific Keycloak realm
        
        Args:
            issuer_uri: Full issuer URI (e.g., https://idm.timesmart.io/realms/smmc-uat-prod)
        """
        self.issuer_uri = issuer_uri
        self.jwks_uri = f"{issuer_uri}/protocol/openid-connect/certs"
        self.realm = issuer_uri.split("/realms/")[-1]
    
    async def get_jwks(self) -> Dict[str, Any]:
        """Fetch and cache JWKS from Keycloak"""
        # Return cached JWKS if still valid (1 hour cache)
        if self.realm in _jwks_cache:
            if self.realm in _jwks_expiry:
                if datetime.now() < _jwks_expiry[self.realm]:
                    return _jwks_cache[self.realm]
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.jwks_uri, timeout=10.0)
                response.raise_for_status()
                jwks = response.json()
                
                # Cache for 1 hour
                _jwks_cache[self.realm] = jwks
                _jwks_expiry[self.realm] = datetime.now() + timedelta(hours=1)
                
                logger.debug(f"Fetched JWKS from {self.realm}")
                return jwks
        except Exception as e:
            logger.error(f"Failed to fetch JWKS from {self.issuer_uri}: {str(e)}")
            raise
    
    def _get_public_key(self, token: str, jwks: Dict[str, Any]) -> Optional[str]:
        """Extract public key from JWKS for token"""
        try:
            # Decode header without verification to get kid
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
            
            if not kid:
                logger.warning("Token missing 'kid' in header")
                return None
            
            # Find matching key in JWKS
            for key in jwks.get("keys", []):
                if key.get("kid") == kid:
                    # Convert JWK to PEM format
                    from jwclient import JWK
                    jwk_obj = JWK.from_json(json.dumps(key))
                    return jwk_obj.serialize(private_key=False)
            
            logger.warning(f"No matching key found for kid: {kid}")
            return None
        except Exception as e:
            logger.error(f"Failed to extract public key: {str(e)}")
            return None
    
    async def validate(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Validate JWT token and return claims
        
        Args:
            token: JWT token string
            
        Returns:
            Token claims dict or None if invalid
        """
        try:
            # Check cache first
            if token in _token_cache:
                cached = _token_cache[token]
                if cached.get("expires_at") > datetime.now().timestamp():
                    return cached.get("claims")
            
            # Fetch JWKS
            jwks = await self.get_jwks()
            
            # Get public key
            public_key = self._get_public_key(token, jwks)
            if not public_key:
                return None
            
            # Validate and decode token
            claims = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                issuer=self.issuer_uri,
                options={"verify_aud": False},  # Don't verify audience for gateway
            )
            
            # Cache token claims
            exp = claims.get("exp")
            if exp:
                _token_cache[token] = {
                    "claims": claims,
                    "expires_at": exp,
                }
            
            logger.debug(f"Token valid for user: {claims.get('preferred_username')}")
            return claims
        
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Token validation error: {str(e)}")
            return None


class KeycloakConfig:
    """Multi-realm Keycloak configuration"""
    
    REALMS = {
        "smmc-uat-prod": "https://idm.timesmart.io/realms/smmc-uat-prod",
        "timesmart-master-uat": "https://idm.timesmart.io/realms/timesmart-master-uat",
        "tenethealth-uat-prod": "https://idm.timesmart.io/realms/tenethealth-uat-prod",
    }
    
    @classmethod
    def get_validators(cls) -> Dict[str, KeycloakTokenValidator]:
        """Get validators for all realms"""
        return {
            realm: KeycloakTokenValidator(issuer_uri)
            for realm, issuer_uri in cls.REALMS.items()
        }


def extract_roles(claims: Dict[str, Any]) -> List[str]:
    """
    Extract roles from Keycloak token claims
    
    Supports:
    - realm_access.roles
    - resource_access.*.roles
    """
    roles = []
    
    # Realm roles
    if "realm_access" in claims and "roles" in claims["realm_access"]:
        roles.extend(claims["realm_access"]["roles"])
    
    # Resource/client roles
    if "resource_access" in claims:
        for resource, access in claims["resource_access"].items():
            if isinstance(access, dict) and "roles" in access:
                roles.extend(access["roles"])
    
    return list(set(roles))  # Remove duplicates


def get_username(claims: Dict[str, Any]) -> str:
    """Extract username from claims (preferred_username)"""
    return claims.get("preferred_username") or claims.get("sub") or "unknown"
