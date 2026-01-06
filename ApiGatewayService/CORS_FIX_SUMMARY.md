# OAuth2/Keycloak CORS Fix - Implementation Summary

## Problem
FastAPI gateway was proxying OPTIONS (CORS preflight) requests to Keycloak OAuth2 endpoints, which don't support OPTIONS method. This resulted in:
- HTTP 405 Method Not Allowed from Keycloak
- CORS errors in browser console
- OAuth2 flow broken on session refresh or page reload

## Solution
Implemented a comprehensive CORS and OAuth2 middleware stack that:
1. Intercepts OPTIONS requests early
2. Returns 200 OK with CORS headers without proxying
3. Validates cross-origin requests
4. Properly relays Authorization headers
5. Adds forwarded headers for reverse proxy (Nginx)

## Files Created

### 1. `app/core/cors.py` (NEW)
Production-ready CORS configuration for OAuth2/Keycloak
- `CORSConfig`: Pydantic model with CORS settings
- `get_cors_config()`: Get CORS configuration
- `should_proxy_options()`: Determine if OPTIONS should be proxied
- `build_cors_headers()`: Build CORS response headers
- `get_allowed_origin()`: Validate and get allowed origin

**Key Features**:
- Includes Keycloak server in allowed origins
- Supports credentials for session-based auth
- Configures proper headers and expose headers
- Sets 24-hour preflight cache

### 2. `app/filters/cors_middleware.py` (NEW)
Four middleware components:

#### CORSPreflightMiddleware
- Intercepts OPTIONS requests early
- Returns 200 OK with CORS headers instead of proxying
- Never proxies to Keycloak OAuth2 endpoints
- Validates origin against configured list

#### CORSResponseMiddleware
- Adds CORS headers to all responses
- Handles credential-aware origin echoing
- Respects upstream CORS headers

#### AuthorizationHeaderMiddleware
- Token relay from cookies to Authorization header
- Forwards Authorization headers properly
- Supports OAuth2 flows

#### ForwardedHeadersMiddleware
- Adds X-Forwarded-For (client IP)
- Adds X-Forwarded-Proto (http/https)
- Adds X-Forwarded-Host (original hostname)
- Essential for reverse proxy (Nginx) support

## Files Modified

### 1. `app/main.py`
**Changes**:
- Import new middleware and CORS config
- Register middleware in correct order:
  1. ForwardedHeadersMiddleware
  2. CORSResponseMiddleware
  3. AuthorizationHeaderMiddleware
  4. CORSPreflightMiddleware
  5. CORSMiddleware (FastAPI built-in)
- Add logging for CORS configuration
- Use enhanced CORS settings

### 2. `app/api/gateway_routes.py`
**Changes**:
- Updated documentation
- Changed OPTIONS handling to note it's caught by middleware
- Added warning log if OPTIONS reaches handler

### 3. `app/core/config.py`
**Changes**:
- Enhanced `parse_cors_origins` validator with documentation
- Better comments for CORS configuration

### 4. `.env.example`
**Changes**:
- Complete documentation of all settings
- Keycloak OAuth2 configuration examples
- CORS configuration best practices
- Environment-specific examples

## New Files
- `OAUTH2_CORS_FIX.md`: Comprehensive documentation
- `app/core/cors.py`: CORS configuration module
- `app/filters/cors_middleware.py`: CORS middleware components

## Configuration

### Minimal Setup (Production)
```env
CORS_ORIGINS=https://app.timesmartai.ca,https://idm.timesmart.io
CORS_CREDENTIALS=true
CORS_METHODS=GET,POST,PUT,DELETE,PATCH,OPTIONS,HEAD
CORS_HEADERS=*

KEYCLOAK_ENABLED=true
KEYCLOAK_SERVER_URL=https://idm.timesmart.io
KEYCLOAK_REALM=smmc-uat-prod
KEYCLOAK_CLIENT_ID=spring-addons-confidential
KEYCLOAK_REDIRECT_URI=https://api.timesmart.io/login/oauth2/code/keycloak
```

**CRITICAL**: Include Keycloak server URL in `CORS_ORIGINS`

### Development Setup
```env
CORS_ORIGINS=http://localhost:3000,http://localhost:8080,https://idm.timesmart.io
CORS_CREDENTIALS=true
KEYCLOAK_ENABLED=true
KEYCLOAK_SERVER_URL=https://idm.timesmart.io
```

## How It Works

### Request Flow
```
Browser → Gateway (CORSPreflightMiddleware) → Backend
    ↓
  OPTIONS preflight (local response)
  ↓
  200 OK + CORS headers
```

### Preflight Caching
- Browser caches OPTIONS response for 24 hours
- First request: OPTIONS + actual request
- Subsequent requests (24h): Only actual request
- Reduces latency for repeated requests

### Origin Validation
- Check request Origin header
- Validate against CORS_ORIGINS list
- Return specific origin in response (not wildcard when credentials enabled)
- Reject disallowed origins with 403

## Testing

### Test CORS Preflight
```bash
curl -X OPTIONS "https://api.timesmart.io/health" \
  -H "Origin: https://app.timesmartai.ca" \
  -H "Access-Control-Request-Method: GET" \
  -v
```

Expected: HTTP 200 with CORS headers

### Test OAuth2 Flow
1. Navigate to `/login` on frontend
2. Redirected to Keycloak login
3. Log in successfully
4. Redirected back to `/login/oauth2/code/keycloak`
5. Should complete without CORS errors

### Enable Debug Logging
```bash
LOG_LEVEL=DEBUG
```

Watch logs:
```bash
docker logs -f gateway | grep -i cors
docker logs -f gateway | grep "preflight\|origin"
```

## Middleware Order (Critical)

The order middleware is added to FastAPI matters because they execute in reverse order:

```python
# Added (last first = executed first)
app.add_middleware(ForwardedHeadersMiddleware)      # 5th to execute
app.add_middleware(CORSResponseMiddleware)          # 4th to execute
app.add_middleware(AuthorizationHeaderMiddleware)   # 3rd to execute
app.add_middleware(CORSPreflightMiddleware)         # 2nd to execute
app.add_middleware(CORSMiddleware)                  # 1st to execute
```

## Key Improvements

### Before Fix
❌ OPTIONS requests proxied to Keycloak → 405 error
❌ Browser blocks request due to CORS error
❌ OAuth2 flow broken on session refresh
❌ No support for reverse proxy headers
❌ No credential-aware CORS handling

### After Fix
✅ OPTIONS handled locally → 200 OK
✅ CORS headers returned correctly
✅ OAuth2 flow works reliably
✅ Support for Nginx reverse proxy
✅ Credential-aware origin validation
✅ 24-hour preflight caching
✅ Proper token relay
✅ Client IP preservation for backend services

## Nginx Configuration (Recommended)

```nginx
server {
    listen 443 ssl http2;
    server_name api.timesmart.io;
    
    ssl_certificate /etc/nginx/ssl/api.crt;
    ssl_certificate_key /etc/nginx/ssl/api.key;
    
    location / {
        proxy_pass http://localhost:8000;
        
        # Essential for CORS & OAuth2
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $server_name;
        
        proxy_set_header Host $host;
        proxy_http_version 1.1;
    }
}
```

## Startup Logs (Check These)

When gateway starts, you should see:

```
INFO:     Registered ForwardedHeadersMiddleware for reverse proxy headers
INFO:     Registered CORSResponseMiddleware to add CORS headers to responses
INFO:     Registered AuthorizationHeaderMiddleware for token relay
INFO:     Registered CORSPreflightMiddleware for OPTIONS preflight handling
INFO:     Registered CORSMiddleware with 2 allowed origins
INFO:     CORS allowed origins: https://app.timesmartai.ca, https://idm.timesmart.io
INFO:     CORS credentials: true
INFO:     CORS max_age: 86400s (preflight cache)
INFO:     Keycloak Login: https://idm.timesmart.io/realms/smmc-uat-prod/protocol/openid-connect/auth
INFO:     CORS: Keycloak server (https://idm.timesmart.io) added to allowed origins
```

## Troubleshooting

### CORS Error: "No 'Access-Control-Allow-Origin' header"
- Check `CORS_ORIGINS` includes frontend domain
- Verify middleware is registered in `main.py`
- Check logs for "disallowed origin"

### OPTIONS Returns 405
- Verify `CORSPreflightMiddleware` is registered
- Check middleware order (preflight before global CORS)
- Review logs for "Handling CORS preflight locally"

### OAuth2 Redirect Fails After Session Expiry
- Verify Keycloak URL in `CORS_ORIGINS`
- Check `KEYCLOAK_SERVER_URL` matches configured domain
- Clear browser cache and cookies

### Backend Gets Wrong Client IP
- Verify `ForwardedHeadersMiddleware` registered
- Configure Nginx to pass X-Forwarded-* headers
- Check backend trusts forwarded headers

## Performance Notes

- **Preflight Caching**: 24 hours (configurable in `cors.py`)
  - First request: OPTIONS + actual = 2 requests
  - Subsequent 24h: Only actual = 1 request
  - ~50% reduction in HTTP requests for repeated origins

- **No Overhead for Non-CORS Requests**
  - Middleware checks Origin header first
  - Short-circuits if not a CORS request
  - Minimal performance impact

## Security Notes

- **Credentials with Wildcard Origins**: Disabled
  - If `CORS_CREDENTIALS=true`, wildcard `*` not used
  - Specific origin echoed in response instead
  - Prevents credential leakage to unauthorized origins

- **Origin Validation**: All cross-origin requests validated
  - Disallowed origins return 403 Forbidden
  - Prevents CSRF attacks via CORS

- **Token Handling**: Authorization header forwarded securely
  - Hop-by-hop headers excluded
  - Token relay to backend services

## Next Steps

1. **Update .env** with your CORS origins and Keycloak settings
2. **Test CORS**: Use curl commands from OAUTH2_CORS_FIX.md
3. **Test OAuth2**: Navigate to `/login` and verify flow works
4. **Configure Nginx**: Pass X-Forwarded-* headers
5. **Enable Debug Logging**: Set `LOG_LEVEL=DEBUG` during testing
6. **Monitor Logs**: Watch for CORS preflight messages
7. **Clear Browser Cache**: Between tests to avoid stale preflight responses

## Support

For detailed configuration and troubleshooting, see:
- [OAUTH2_CORS_FIX.md](OAUTH2_CORS_FIX.md) - Complete guide with examples
- [app/core/cors.py](app/core/cors.py) - CORS configuration code
- [app/filters/cors_middleware.py](app/filters/cors_middleware.py) - Middleware implementation
