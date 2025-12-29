# Keycloak Authentication Integration - Implementation Summary

## Changes Made

### 1. New Core Modules

#### `app/core/keycloak.py`
- **KeycloakTokenValidator**: Validates JWT tokens from Keycloak realms
  - Fetches and caches JWKS from Keycloak
  - Validates JWT signatures using RS256
  - Supports 3 realms: smmc-uat-prod, timesmart-master-uat, tenethealth-uat-prod
  - 1-hour JWKS cache for performance
  
- **KeycloakConfig**: Multi-realm configuration
  - Maps realm names to issuer URIs
  - Provides validators for all realms
  
- **Helper Functions**:
  - `extract_roles()`: Extracts roles from realm_access and resource_access claims
  - `get_username()`: Extracts preferred_username from claims

#### `app/core/auth_dependencies.py`
- **FastAPI Dependencies** for use in route handlers
  - `get_token_from_header()`: Extract Bearer token from Authorization header
  - `get_current_user()`: Validate token and return claims (401 if invalid)
  - `require_roles()`: Check if user has required roles (403 if insufficient)
  - `create_role_dependency()`: Factory for creating role-checking dependencies

### 2. Updated Existing Files

#### `app/core/config.py`
- Updated docstring to reflect Keycloak integration
- Already had Keycloak config fields (KEYCLOAK_ENABLED, KEYCLOAK_SERVER_URL, etc.)

#### `app/api/gateway_routes.py`
- **Added Token Validation**:
  - `_is_public_route()`: Check if path requires authentication
  - `_validate_token_if_required()`: Validate JWT for protected routes
  
- **Public Routes** (no auth required):
  - /login, /oauth2, /, /home, /app, /docs, /health, /actuator/health
  - /user-management-service/user/ssoid/**
  - /entity-service/entityID, /entity-service/entity/logo, /entity-service/entity/allEntity
  
- **Protected Routes** (JWT required):
  - All other paths except public routes
  - Returns 401 if token missing/invalid
  - Returns 403 if role check fails (when implemented)
  
- **Logging Enhanced**:
  - Logs authenticated user, realm, and roles
  - Logs authentication failures

#### `requirements.txt`
- Added JWT validation packages:
  - PyJWT==2.8.1
  - python-jose==3.3.0
  - jwclient==0.8.1

### 3. Authentication Flow

**For Protected Routes:**
1. Gateway receives request
2. Extracts Bearer token from Authorization header
3. Validates token signature using Keycloak JWKS
4. Tries validation against all 3 realms
5. If valid:
   - Extracts user claims
   - Logs authentication success
   - Forwards request with Authorization header to backend
6. If invalid:
   - Returns 401 Unauthorized
   - Logs authentication failure

**For Public Routes:**
- No token validation required
- Request forwarded directly to backend

### 4. Usage Examples

#### Validating Token in Route Handler
```python
from fastapi import Depends
from app.core.auth_dependencies import get_current_user

@app.get("/protected-route")
async def protected_route(user = Depends(get_current_user)):
    # user = {"claims": {...}, "realm": "...", "username": "..."}
    return {"message": f"Hello {user['username']}"}
```

#### Checking Specific Roles
```python
from app.core.auth_dependencies import require_roles

@app.get("/admin-route")
async def admin_route(user = Depends(require_roles(["ADMIN", "MANAGER"]))):
    # Only users with ADMIN or MANAGER role can access
    return {"message": "Admin access granted"}
```

#### Creating Role Dependencies
```python
from app.core.auth_dependencies import create_role_dependency

admin_required = create_role_dependency(["ADMIN"])

@app.delete("/delete-user")
async def delete_user(user = Depends(admin_required)):
    return {"message": "User deleted"}
```

### 5. Configuration (`.env`)

```
KEYCLOAK_ENABLED=true
KEYCLOAK_SERVER_URL=https://idm.timesmart.io
KEYCLOAK_REALM=smmc-uat-prod
KEYCLOAK_CLIENT_ID=spring-addons-confidential
KEYCLOAK_CLIENT_SECRET=SIfNoIQ7aUnW6pvwT2I9YjYhZKhRIlUd
KEYCLOAK_REDIRECT_URI=https://smmc-uat-prod.timesmartai.ca/auth/callback
POST_LOGIN_REDIRECT_PATH=/home/
POST_LOGOUT_REDIRECT_PATH=/home
```

### 6. Supported Keycloak Realms

1. **smmc-uat-prod** → https://idm.timesmart.io/realms/smmc-uat-prod
2. **timesmart-master-uat** → https://idm.timesmart.io/realms/timesmart-master-uat
3. **tenethealth-uat-prod** → https://idm.timesmart.io/realms/tenethealth-uat-prod

Token is validated against all realms. If valid in any realm, user is authenticated.

### 7. Role Extraction

Roles are extracted from two sources in JWT claims:
- `realm_access.roles[]` - Realm-wide roles
- `resource_access.{client_id}.roles[]` - Client-specific roles

All extracted roles are deduplicated and logged.

### 8. Error Handling

- **401 Unauthorized**: Missing token, invalid signature, expired token
- **403 Forbidden**: Valid token but missing required roles
- **503 Service Unavailable**: Cannot reach backend service
- **502 Bad Gateway**: Error forwarding request to backend

All errors are logged with context for debugging.

### 9. Security Notes

- JWKS is cached for 1 hour to reduce Keycloak load
- Token validation cache prevents duplicate validations
- RS256 signature verification ensures token authenticity
- Public routes list is hardcoded (cannot be bypassed)
- Authorization header is forwarded to backend (TokenRelay)

### 10. Backward Compatibility

- Existing gateway routing logic unchanged
- API signatures remain the same
- Can disable Keycloak via `KEYCLOAK_ENABLED=false` to bypass auth
- All public routes still accessible without auth

## Testing Checklist

- [ ] Public routes accessible without token
- [ ] Protected routes return 401 without token
- [ ] Protected routes accept valid JWT
- [ ] Token validated against all 3 realms
- [ ] Roles extracted correctly from claims
- [ ] Role checks return 403 for insufficient permissions
- [ ] Authorization header forwarded to backend
- [ ] Logging shows authenticated user and realm
- [ ] JWKS cache works (no errors on repeated requests)
- [ ] Application starts successfully with new modules

