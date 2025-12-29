# Quick Reference: Keycloak Authentication

## Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure `.env`
```
KEYCLOAK_ENABLED=true
KEYCLOAK_SERVER_URL=https://idm.timesmart.io
KEYCLOAK_REALM=smmc-uat-prod
```

### 3. Restart Application
```bash
./startup.sh start
```

---

## Using Authentication in Routes

### Basic Protected Route
```python
from fastapi import Depends
from app.core.auth_dependencies import get_current_user

@app.get("/protected")
async def protected(user = Depends(get_current_user)):
    return {"username": user["username"]}
```

### Admin-Only Route
```python
from app.core.auth_dependencies import create_role_dependency

admin_only = create_role_dependency(["ADMIN"])

@app.delete("/admin/users/{id}")
async def delete_user(id: int, user = Depends(admin_only)):
    return {"deleted": True}
```

### Multiple Roles Allowed
```python
manager_or_admin = create_role_dependency(["MANAGER", "ADMIN"])

@app.post("/reports")
async def create_report(user = Depends(manager_or_admin)):
    return {"report": "created"}
```

### Custom Authorization Logic
```python
from fastapi import HTTPException, status

@app.get("/data")
async def get_data(user = Depends(get_current_user)):
    if "VIEWER" not in user["roles"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Need VIEWER role"
        )
    return {"data": "sensitive"}
```

---

## Public Routes (No Auth Required)

These routes bypass authentication:
- `/`
- `/home`
- `/app`
- `/login`
- `/oauth2`
- `/docs`
- `/health`
- `/actuator/health`
- `/user-management-service/user/ssoid/**`
- `/entity-service/entityID`
- `/entity-service/entity/logo`
- `/entity-service/entity/allEntity`

---

## HTTP Status Codes

| Code | Meaning | Cause |
|------|---------|-------|
| 200 | OK | Request successful |
| 401 | Unauthorized | Missing/invalid token |
| 403 | Forbidden | Insufficient permissions |
| 503 | Service Unavailable | Cannot reach backend |
| 502 | Bad Gateway | Error forwarding request |

---

## Testing with curl

### Public Route (No Token)
```bash
curl http://localhost:8000/
```

### Protected Route (No Token)
```bash
curl http://localhost:8000/protected
# Returns 401 Unauthorized
```

### Protected Route (Valid Token)
```bash
curl -H "Authorization: Bearer eyJhbGc..." \
     http://localhost:8000/protected
```

### Admin Route (Admin Token)
```bash
curl -X DELETE \
     -H "Authorization: Bearer eyJhbGc..." \
     http://localhost:8000/admin/users/123
```

---

## Debugging

### Check if Token is Valid
```bash
# Copy token from Authorization header
export TOKEN="eyJhbGc..."

# Test protected endpoint
curl -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/protected
```

### Check Logs for Authentication Info
```bash
# Look for lines like:
# "Authenticated user: john from realm: smmc-uat-prod with roles: ADMIN"
# "Token validation failed for all realms"
```

### Verify JWKS is Cached
```bash
# First request fetches JWKS
# Subsequent requests within 1 hour use cache
# Check logs for "Fetched JWKS from smmc-uat-prod"
```

---

## Supported Keycloak Realms

| Realm | Issuer URI |
|-------|-----------|
| smmc-uat-prod | https://idm.timesmart.io/realms/smmc-uat-prod |
| timesmart-master-uat | https://idm.timesmart.io/realms/timesmart-master-uat |
| tenethealth-uat-prod | https://idm.timesmart.io/realms/tenethealth-uat-prod |

Token is validated against all realms automatically.

---

## Extracting User Information

From `user` object in handlers:
```python
user["username"]     # preferred_username from JWT
user["realm"]        # Which Keycloak realm authenticated user
user["roles"]        # List of all user roles
user["claims"]       # Full JWT claims dictionary
```

From `user["claims"]`:
```python
user["claims"]["email"]              # User email
user["claims"]["name"]               # Full name
user["claims"]["given_name"]         # First name
user["claims"]["family_name"]        # Last name
user["claims"]["realm_access"]       # Realm roles
user["claims"]["resource_access"]    # Client roles
```

---

## Disabling Authentication (Development Only)

```env
KEYCLOAK_ENABLED=false
```

When disabled:
- All protected routes return None for user
- No token validation occurs
- Useful for testing without Keycloak

---

## Common Issues

### 401 Unauthorized on Protected Route
- Check Authorization header is present: `Authorization: Bearer <token>`
- Verify token is valid at https://jwt.io (decode without verification)
- Check token hasn't expired
- Ensure Keycloak server is accessible

### 403 Forbidden on Role-Based Route
- Verify user has required role
- Check role name spelling (case-sensitive)
- Roles come from realm_access.roles and resource_access.*.roles

### Keycloak Connection Error
- Verify KEYCLOAK_SERVER_URL is correct
- Check network connectivity to https://idm.timesmart.io
- Ensure firewall allows outbound HTTPS

### JWKS Cache Not Working
- Check logs for "Fetched JWKS" message
- JWKS cached for 1 hour
- Restart app to clear cache manually

---

## Files Modified

- `app/core/keycloak.py` - New: JWT validation logic
- `app/core/auth_dependencies.py` - New: FastAPI dependencies
- `app/core/config.py` - Updated: Added Keycloak config
- `app/api/gateway_routes.py` - Updated: Token validation
- `requirements.txt` - Updated: Added JWT packages
- `.env` - Updated: Added Keycloak settings

---

## API Gateway Behavior

Gateway acts as **token validator only**:
1. Validates JWT signature from Keycloak
2. Checks token expiration
3. Extracts user roles
4. Forwards Authorization header to backend services
5. **Does NOT handle OAuth2 login/callback**

Backend services handle:
- Login flow
- OAuth2 authorization code exchange
- Session management
- Application-specific authorization

---

## Security Considerations

✅ **Enabled by Default:**
- RS256 signature verification
- Issuer validation
- Expiration check
- JWKS caching (1 hour)
- Role-based access control

⚠️ **Note:**
- Audience (aud) claim NOT verified (gateway serves multiple clients)
- Token cache until expiration (memory usage acceptable)
- Public routes list is hardcoded (cannot be bypassed)

---

## Performance

- JWKS fetched once per hour
- Token claims cached until expiration
- ~5ms per request validation (network cached)
- No database queries in gateway
- Minimal memory overhead

---

## Troubleshooting Checklist

- [ ] KEYCLOAK_ENABLED=true in .env
- [ ] Requirements installed: pip install -r requirements.txt
- [ ] Keycloak server accessible: curl https://idm.timesmart.io
- [ ] Valid JWT token in request
- [ ] Token not expired: jwt.io decode check
- [ ] User has required role: check Keycloak console
- [ ] Authorization header format: "Authorization: Bearer <token>"
- [ ] Check application logs for error messages

---

## More Information

See `KEYCLOAK_INTEGRATION.md` for detailed implementation guide.
See `EXAMPLE_AUTH_USAGE.py` for code examples.
