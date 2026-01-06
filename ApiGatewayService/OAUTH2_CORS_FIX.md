# OAuth2/Keycloak CORS Configuration Guide

## Problem Summary

When using OAuth2 with Keycloak behind a gateway, browsers send CORS preflight (OPTIONS) requests before the actual authentication request. If the gateway tries to proxy these OPTIONS requests to Keycloak, they fail with:

```
HTTP 405 Method Not Allowed
```

This causes CORS errors in the browser and blocks the OAuth2 flow after session expiry or page refresh.

## Root Cause

1. Browser sends `OPTIONS /realms/{realm}/protocol/openid-connect/auth`
2. Gateway proxies this to Keycloak server
3. Keycloak OAuth2 endpoints don't support OPTIONS method → Returns 405
4. Browser receives 405 error → Blocks actual request due to CORS policy

## Solution Architecture

### 1. **CORSPreflightMiddleware** (New)
Intercepts OPTIONS requests early in the middleware chain and:
- Checks if request origin is allowed
- Returns 200 OK with CORS headers instead of proxying
- Never proxies OPTIONS to Keycloak OAuth2 endpoints

**File**: `app/filters/cors_middleware.py`

### 2. **Enhanced CORS Configuration** (New)
Comprehensive CORS settings for OAuth2:
- Includes Keycloak server in allowed origins
- Supports credentials for session-based auth
- Configures proper headers and expose headers
- Sets preflight cache time (24 hours)

**File**: `app/core/cors.py`

### 3. **ForwardedHeadersMiddleware** (New)
Essential for reverse proxy (Nginx/HAProxy):
- Adds `X-Forwarded-For` (client IP)
- Adds `X-Forwarded-Proto` (http/https)
- Adds `X-Forwarded-Host` (original hostname)
- Preserves existing headers if already present

**File**: `app/filters/cors_middleware.py`

### 4. **AuthorizationHeaderMiddleware** (New)
Token relay support:
- Forwards Authorization header as-is
- Converts cookies to Authorization header when needed
- Supports OAuth2 flows

**File**: `app/filters/cors_middleware.py`

## Configuration

### Environment Variables

#### CORS Origins (Include Keycloak)
```bash
# Comma-separated list
CORS_ORIGINS=http://localhost:3000,https://app.timesmartai.ca,https://idm.timesmart.io

# Or wildcard (allow all origins)
CORS_ORIGINS=*
```

#### CORS Methods
```bash
CORS_METHODS=GET,POST,PUT,DELETE,PATCH,OPTIONS,HEAD
```

#### CORS Headers
```bash
CORS_HEADERS=*  # or specific headers separated by commas
```

#### CORS Credentials
```bash
CORS_CREDENTIALS=true  # Required for OAuth2 with session cookies
```

#### Keycloak Configuration
```bash
KEYCLOAK_ENABLED=true
KEYCLOAK_SERVER_URL=https://idm.timesmart.io
KEYCLOAK_REALM=smmc-uat-prod
KEYCLOAK_CLIENT_ID=spring-addons-confidential
KEYCLOAK_REDIRECT_URI=https://api.timesmart.io/login/oauth2/code/keycloak
```

### .env Example
```env
# Server
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
ENVIRONMENT=production

# Frontend
REACT_URI=https://app.timesmartai.ca
FLUTTER_URI=https://app.timesmartai.ca

# CORS - IMPORTANT: Include Keycloak server URL
CORS_ORIGINS=https://app.timesmartai.ca,https://idm.timesmart.io
CORS_CREDENTIALS=true
CORS_METHODS=GET,POST,PUT,DELETE,PATCH,OPTIONS,HEAD
CORS_HEADERS=*

# Keycloak OAuth2
KEYCLOAK_ENABLED=true
KEYCLOAK_SERVER_URL=https://idm.timesmart.io
KEYCLOAK_REALM=smmc-uat-prod
KEYCLOAK_CLIENT_ID=spring-addons-confidential
KEYCLOAK_CLIENT_SECRET=<secret>
KEYCLOAK_REDIRECT_URI=https://api.timesmart.io/login/oauth2/code/keycloak

# Backend Services
USER_MANAGEMENT_SERVICE_URL=http://user-service:8001
CONTRACT_MANAGEMENT_SERVICE_URL=http://contract-service:8002
ENTITY_SERVICE_URL=http://entity-service:8003
TIMESHEET_MANAGEMENT_SERVICE_URL=http://timesheet-service:8004
NOTIFICATION_SERVICE_URL=http://notification-service:8005
```

## How It Works

### Request Flow

```
Browser                    FastAPI Gateway               Keycloak
   │                              │                         │
   ├─ OPTIONS preflight ────────→ │                         │
   │  (CORS check)                │                         │
   │                    (CORSPreflightMiddleware)           │
   │                    Returns 200 OK + CORS headers       │
   │ ←────────────────────────────┤                         │
   │                              │                         │
   ├─ POST /auth (Bearer token)─→ │                         │
   │                              ├─ Forward to Keycloak ──→ │
   │                              │                         │ (OAuth2 code)
   │                              │ ←─────────────────────── │
   │ ←────────────────────────────┤                         │
```

### Key Points

1. **Preflight Caching**: Browsers cache preflight responses for 24 hours (configurable via `max_age`)
   - First request: OPTIONS + actual request
   - Subsequent requests (24h): Only actual request

2. **Origin Validation**: 
   - Check against configured `CORS_ORIGINS`
   - Return specific origin in response (not wildcard when credentials=true)

3. **Header Forwarding**:
   - Authorization header forwarded as-is
   - All standard and custom headers preserved
   - Hop-by-hop headers (Connection, Transfer-Encoding) excluded

4. **Reverse Proxy Support**:
   - Forwarded headers added automatically
   - Backend services see original client IP and protocol
   - Critical for proper HTTPS/SSL termination at Nginx

## Middleware Stack (Order Matters)

```python
app.add_middleware(ForwardedHeadersMiddleware)      # 1. Add forwarded headers
app.add_middleware(CORSResponseMiddleware)          # 2. Add CORS headers to responses  
app.add_middleware(AuthorizationHeaderMiddleware)   # 3. Token relay
app.add_middleware(CORSPreflightMiddleware)         # 4. Handle OPTIONS locally
app.add_middleware(CORSMiddleware)                  # 5. FastAPI built-in CORS
```

Each middleware is applied to the request in **reverse order** (last registered = first executed).

## Testing CORS Configuration

### Test 1: Preflight to Keycloak OAuth2 Endpoint
```bash
curl -X OPTIONS \
  "https://api.timesmart.io/realms/smmc-uat-prod/protocol/openid-connect/auth" \
  -H "Origin: https://app.timesmartai.ca" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: Authorization, Content-Type" \
  -v
```

**Expected Response**:
```
HTTP/1.1 200 OK
Access-Control-Allow-Origin: https://app.timesmartai.ca
Access-Control-Allow-Methods: GET, POST, PUT, DELETE, PATCH, OPTIONS, HEAD
Access-Control-Allow-Headers: Content-Type, Authorization, ...
Access-Control-Allow-Credentials: true
Access-Control-Max-Age: 86400
```

### Test 2: Browser CORS Check
Open browser console and test:
```javascript
// In browser console on https://app.timesmartai.ca
fetch('https://api.timesmart.io/health', {
  method: 'GET',
  headers: {
    'Content-Type': 'application/json',
  }
}).then(r => r.json()).then(console.log)
```

**Success**: Returns `{"status": "healthy", ...}`
**Failure**: See CORS error in console

### Test 3: OAuth2 Flow
1. Navigate to `/login` on your app
2. Browser redirected to Keycloak login
3. Log in successfully
4. Browser redirected back to `/login/oauth2/code/keycloak`
5. Should complete login without CORS errors

## Common Issues & Solutions

### Issue 1: "CORS policy blocked request"
**Symptom**: Browser console shows CORS error

**Solutions**:
1. Verify `CORS_ORIGINS` includes your frontend domain
2. Verify `CORS_ORIGINS` includes Keycloak server URL
3. Check that `CORS_CREDENTIALS=true` when using OAuth2
4. Ensure middleware is properly registered in `main.py`

### Issue 2: "405 Method Not Allowed"
**Symptom**: Gateway returns 405 for OPTIONS requests

**Solutions**:
1. Verify `CORSPreflightMiddleware` is registered
2. Check that middleware order is correct (preflight before global CORS)
3. Review logs for "Handling CORS preflight locally" message
4. Verify `should_proxy_options()` returns False for Keycloak paths

### Issue 3: OAuth2 Redirect Fails After Session Expiry
**Symptom**: Browser redirected to login, but gets CORS error

**Solutions**:
1. Verify Keycloak server URL in `CORS_ORIGINS`
2. Check that `ForwardedHeadersMiddleware` is registered
3. Verify `KEYCLOAK_SERVER_URL` matches the domain in `CORS_ORIGINS`
4. Clear browser cache and cookies, try again

### Issue 4: Backend Services Receiving Wrong Client IP
**Symptom**: Backend services see gateway IP instead of real client IP

**Solutions**:
1. Verify `ForwardedHeadersMiddleware` is registered
2. Configure Nginx to pass forwarded headers:
   ```nginx
   proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
   proxy_set_header X-Forwarded-Proto $scheme;
   proxy_set_header X-Forwarded-Host $server_name;
   ```
3. Backend services must trust X-Forwarded-* headers

## Nginx Configuration for Reverse Proxy

```nginx
server {
    listen 443 ssl http2;
    server_name api.timesmart.io;
    
    # SSL certificates
    ssl_certificate /etc/nginx/ssl/api.crt;
    ssl_certificate_key /etc/nginx/ssl/api.key;
    
    # Gateway proxy
    location / {
        # Forward to FastAPI gateway
        proxy_pass http://localhost:8000;
        
        # Essential: Pass forwarded headers (FOR CORS & OAUTH2)
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $server_name;
        proxy_set_header X-Forwarded-Port $server_port;
        
        # Other important headers
        proxy_set_header Host $host;
        proxy_set_header Connection "upgrade";
        proxy_http_version 1.1;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

## Docker Compose Example

```yaml
version: '3.8'

services:
  nginx:
    image: nginx:latest
    ports:
      - "443:443"
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - gateway

  gateway:
    build: .
    environment:
      - SERVER_HOST=0.0.0.0
      - SERVER_PORT=8000
      - REACT_URI=https://app.timesmartai.ca
      - CORS_ORIGINS=https://app.timesmartai.ca,https://idm.timesmart.io
      - CORS_CREDENTIALS=true
      - KEYCLOAK_ENABLED=true
      - KEYCLOAK_SERVER_URL=https://idm.timesmart.io
      - KEYCLOAK_REALM=smmc-uat-prod
      - KEYCLOAK_CLIENT_ID=spring-addons-confidential
      - USER_MANAGEMENT_SERVICE_URL=http://user-service:8001
      - CONTRACT_MANAGEMENT_SERVICE_URL=http://contract-service:8002
      - ENTITY_SERVICE_URL=http://entity-service:8003
      - TIMESHEET_MANAGEMENT_SERVICE_URL=http://timesheet-service:8004
      - NOTIFICATION_SERVICE_URL=http://notification-service:8005
    ports:
      - "8000:8000"
```

## Monitoring & Logging

### Enable Debug Logging
```bash
LOG_LEVEL=DEBUG
```

### Watch CORS Headers in Logs
```bash
docker logs -f gateway | grep -i cors
```

### Monitor Preflight Requests
```bash
docker logs -f gateway | grep "CORS preflight"
```

### Check Origin Validation
```bash
docker logs -f gateway | grep "allowed origin\|disallowed origin"
```

## Troubleshooting Checklist

- [ ] Keycloak server URL in `CORS_ORIGINS`
- [ ] Frontend origin in `CORS_ORIGINS`
- [ ] `CORS_CREDENTIALS=true`
- [ ] `CORS_METHODS` includes OPTIONS
- [ ] `CORSPreflightMiddleware` registered
- [ ] Middleware order correct in `main.py`
- [ ] `ForwardedHeadersMiddleware` registered
- [ ] Nginx passing X-Forwarded-* headers
- [ ] No log errors for "disallowed origin"
- [ ] Browser DevTools shows proper CORS headers in response

## Files Modified

1. **app/core/cors.py** (NEW)
   - CORS configuration for OAuth2/Keycloak
   - Origin validation logic
   - Header building helpers

2. **app/filters/cors_middleware.py** (NEW)
   - CORSPreflightMiddleware (OPTIONS handling)
   - CORSResponseMiddleware (response headers)
   - AuthorizationHeaderMiddleware (token relay)
   - ForwardedHeadersMiddleware (reverse proxy headers)

3. **app/main.py** (MODIFIED)
   - Register new middleware in correct order
   - Use enhanced CORS config
   - Log CORS configuration on startup

4. **app/api/gateway_routes.py** (MODIFIED)
   - Improved documentation
   - OPTIONS handling note

5. **app/core/config.py** (MODIFIED)
   - Enhanced CORS origin validator
   - Better documentation

## References

- [FastAPI CORS Documentation](https://fastapi.tiangolo.com/tutorial/cors/)
- [Keycloak CORS Documentation](https://www.keycloak.org/docs/latest/server_admin/)
- [MDN CORS Documentation](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS)
- [Spring Cloud Gateway CORS Configuration](https://spring.io/projects/spring-cloud-gateway)
- [RFC 7231 - HTTP Semantics (OPTIONS Method)](https://tools.ietf.org/html/rfc7231#section-4.3.7)
