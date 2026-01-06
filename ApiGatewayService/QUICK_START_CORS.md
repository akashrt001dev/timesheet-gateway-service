# OAuth2/Keycloak CORS Fix - Quick Start Guide

## 🚀 What Was Fixed

Your FastAPI gateway was failing OAuth2/Keycloak authentication on page refresh with:
```
CORS error: No 'Access-Control-Allow-Origin' header
HTTP 405 Method Not Allowed
```

**Root cause**: Browser sent OPTIONS preflight requests to Keycloak, which doesn't support OPTIONS on OAuth2 endpoints.

**Solution**: Added middleware to handle OPTIONS locally and proper CORS configuration.

## ✅ What You Get

- ✅ OPTIONS preflight requests handled locally (200 OK)
- ✅ Keycloak OAuth2 flow works after session refresh
- ✅ CORS headers properly configured
- ✅ Token relay (Authorization header) working
- ✅ Support for reverse proxy (Nginx) with X-Forwarded headers
- ✅ 24-hour preflight caching (reduces latency)

## 📝 Configuration (5 minutes)

### 1. Update `.env` file

**Minimum required changes**:

```env
# Add Keycloak server to CORS origins (CRITICAL!)
CORS_ORIGINS=https://app.timesmartai.ca,https://idm.timesmart.io

# Keep this enabled for OAuth2
CORS_CREDENTIALS=true

# Ensure CORS methods include OPTIONS
CORS_METHODS=GET,POST,PUT,DELETE,PATCH,OPTIONS,HEAD

# Keycloak OAuth2 settings
KEYCLOAK_ENABLED=true
KEYCLOAK_SERVER_URL=https://idm.timesmart.io
KEYCLOAK_REALM=smmc-uat-prod
KEYCLOAK_CLIENT_ID=spring-addons-confidential
KEYCLOAK_REDIRECT_URI=https://api.timesmart.io/login/oauth2/code/keycloak
```

See `.env.example` for all options.

### 2. Restart Gateway

```bash
# Docker
docker-compose restart gateway

# Or uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Check Startup Logs

You should see these messages:

```
Registered CORSPreflightMiddleware for OPTIONS preflight handling
Registered CORSMiddleware with 2 allowed origins
CORS allowed origins: https://app.timesmartai.ca, https://idm.timesmart.io
CORS: Keycloak server (https://idm.timesmart.io) added to allowed origins
```

## 🧪 Quick Test

### Test 1: CORS Preflight
```bash
curl -X OPTIONS "https://api.timesmart.io/health" \
  -H "Origin: https://app.timesmartai.ca" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: Authorization" \
  -v
```

**Expected**: HTTP 200 with these headers:
```
Access-Control-Allow-Origin: https://app.timesmartai.ca
Access-Control-Allow-Methods: GET, POST, PUT, DELETE, PATCH, OPTIONS, HEAD
Access-Control-Allow-Credentials: true
```

### Test 2: OAuth2 Flow in Browser
1. Open your app at `https://app.timesmartai.ca`
2. Click "Login"
3. Should redirect to Keycloak login (no CORS errors)
4. After login, should return to app
5. Should work on page refresh too

## 📋 Files Modified

| File | Change | Purpose |
|------|--------|---------|
| `app/main.py` | Updated | Register CORS middleware in correct order |
| `app/api/gateway_routes.py` | Updated | Improved OPTIONS handling |
| `app/core/config.py` | Updated | Enhanced CORS config validation |
| `app/core/cors.py` | **NEW** | CORS configuration module |
| `app/filters/cors_middleware.py` | **NEW** | CORS & OAuth2 middleware |
| `.env.example` | Updated | Document CORS settings |

## 🔧 Nginx Configuration (If Behind Nginx)

Add these to your Nginx config:

```nginx
location / {
    proxy_pass http://localhost:8000;
    
    # CRITICAL: Forward headers for CORS & OAuth2
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Host $server_name;
    
    proxy_set_header Host $host;
    proxy_http_version 1.1;
}
```

## 🐛 Troubleshooting

### Problem: Still getting CORS error

**Solution**:
1. Check `.env` has Keycloak URL in `CORS_ORIGINS`
2. Clear browser cache (`Ctrl+Shift+Del`)
3. Check startup logs show CORS origins configured
4. Restart gateway

### Problem: OAuth2 redirect still failing

**Solution**:
1. Verify `KEYCLOAK_SERVER_URL` in `.env` matches domain in `CORS_ORIGINS`
2. Check `KEYCLOAK_REDIRECT_URI` is correct (matches Keycloak client settings)
3. Enable debug logging: `LOG_LEVEL=DEBUG`
4. Check logs for "disallowed origin" or preflight handling

### Problem: Backend services getting wrong IP

**Solution**:
1. Verify `ForwardedHeadersMiddleware` is registered (check main.py)
2. If using Nginx, add `X-Forwarded-*` headers (see above)
3. Backend services must trust forwarded headers

### Problem: Gateway slow for repeated requests

**This is normal**. CORS preflight is cached for 24 hours. Subsequent requests should be faster.

To verify:
```bash
# First request: slow (OPTIONS + GET = 2 requests)
curl "https://api.timesmart.io/health"

# Subsequent requests: fast (GET only = 1 request)
curl "https://api.timesmart.io/health"
```

## 📚 More Information

- **Complete guide**: [OAUTH2_CORS_FIX.md](OAUTH2_CORS_FIX.md)
- **Implementation details**: [CORS_FIX_SUMMARY.md](CORS_FIX_SUMMARY.md)
- **Configuration examples**: [.env.example](.env.example)
- **Code**: [app/core/cors.py](app/core/cors.py), [app/filters/cors_middleware.py](app/filters/cors_middleware.py)

## ✨ Key Improvements

**Before**:
- ❌ OAuth2 broken after refresh
- ❌ CORS errors in browser
- ❌ OPTIONS requests proxied to Keycloak → 405 error

**After**:
- ✅ OAuth2 flow reliable
- ✅ CORS properly configured
- ✅ OPTIONS handled locally → 200 OK
- ✅ Preflight caching for performance
- ✅ Reverse proxy support

## 🎯 Next Steps

1. **Update .env** with your Keycloak URL in `CORS_ORIGINS`
2. **Restart gateway**
3. **Test OAuth2 flow** (login → logout → login again)
4. **Monitor logs** during first test

## 💬 Support

If issues persist:
1. Enable debug logging: `LOG_LEVEL=DEBUG`
2. Check logs for CORS-related messages
3. See [OAUTH2_CORS_FIX.md](OAUTH2_CORS_FIX.md) troubleshooting section
4. Verify all configuration in `.env`

---

**That's it!** Your OAuth2/Keycloak CORS issues should now be resolved. 🎉
