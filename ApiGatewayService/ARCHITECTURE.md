# CORS/OAuth2 Fix - Visual Architecture

## Problem Flow (Before Fix)

```
┌─────────────┐
│   Browser   │ https://app.timesmartai.ca
└──────┬──────┘
       │
       │ 1. User clicks "Login"
       │
       ▼
┌──────────────────────────────────────────────────────────┐
│ FastAPI Gateway (api.timesmartai.ca:8000)               │
│                                                          │
│  OPTIONS /realms/.../protocol/openid-connect/auth       │
│  (CORS preflight)                                        │
│                                                          │
│  ❌ PROXIED TO KEYCLOAK (WRONG!)                         │
└──────────────────┬───────────────────────────────────────┘
                   │
                   ▼
            ┌──────────────────┐
            │    Keycloak      │ https://idm.timesmart.io
            │ (idm.timesmart.io)│
            │                  │
            │ Returns:         │
            │ 405 Not Allowed  │
            │ (no OPTIONS      │
            │  support)        │
            └──────────┬───────┘
                       │
                       ▼ HTTP 405
┌──────────────────────────────────────────────────────────┐
│ FastAPI Gateway                                          │
│                                                          │
│ Returns 405 to browser                                   │
└──────────────────┬───────────────────────────────────────┘
                   │
                   ▼ 405 with no CORS headers
┌─────────────┐
│   Browser   │
│             │
│ ❌ CORS Error:
│ "No 'Access-Control-Allow-Origin' header"
│ (blocks request)
└─────────────┘

RESULT: OAuth2 login flow BROKEN on page refresh
```

## Solution Flow (After Fix)

```
┌─────────────┐
│   Browser   │ https://app.timesmartai.ca
└──────┬──────┘
       │
       │ 1. User clicks "Login" (or page refresh)
       │    Browser sends OPTIONS preflight (CORS check)
       │
       ▼
┌──────────────────────────────────────────────────────────┐
│ FastAPI Gateway (api.timesmartai.ca:8000)               │
│                                                          │
│ Request comes in:                                        │
│ OPTIONS /realms/.../protocol/openid-connect/auth        │
│ Origin: https://app.timesmartai.ca                       │
│                                                          │
│ ✅ CORSPreflightMiddleware catches it (EARLY)           │
│    - Check if origin allowed ✓                          │
│    - Check if endpoint should proxy ✗                   │
│    - Return 200 OK with CORS headers                    │
│    - DO NOT PROXY TO KEYCLOAK                           │
└──────────────────┬───────────────────────────────────────┘
                   │
                   ▼ HTTP 200 OK + CORS headers
┌─────────────┐
│   Browser   │
│             │
│ ✅ CORS check passed!
│    (headers present & valid)
│
│ Now send actual request:
│ POST /realms/.../protocol/openid-connect/auth
│ (with Authorization, etc.)
└──────────┬──────┘
           │
           ▼
┌──────────────────────────────────────────────────────────┐
│ FastAPI Gateway                                          │
│                                                          │
│ Request: POST /realms/.../protocol/openid-connect/auth  │
│          with Authorization header                       │
│                                                          │
│ Routes to: /login endpoint                               │
│ (authenticated Keycloak redirect)                        │
└──────────────────┬───────────────────────────────────────┘
                   │
                   ▼
            ┌──────────────────┐
            │    Keycloak      │
            │ (idm.timesmart.io)│
            │                  │
            │ 302 Redirect     │
            │ (to login page)  │
            └──────────┬───────┘
                       │
                       ▼ 302 with Location
┌──────────────────────────────────────────────────────────┐
│ FastAPI Gateway                                          │
│ (with CORS headers added)                                │
└──────────────────┬───────────────────────────────────────┘
                   │
                   ▼ 302 + CORS headers
┌─────────────┐
│   Browser   │
│             │
│ ✅ Redirects to Keycloak login page
│    (no CORS errors)
│
│ User logs in...
│ Redirects back to /login/oauth2/code/*
│ (callback endpoint)
│
│ ✅ OAuth2 flow completes successfully!
└─────────────┘

RESULT: OAuth2 login flow WORKS reliably
        (even on page refresh or session expiry)
```

## Middleware Stack Architecture

```
┌─────────────────────────────────────────────────────────┐
│ Incoming Request                                        │
└────────────────────┬──────────────────────────────────┘
                     │
    ┌────────────────▼────────────────┐
    │ ForwardedHeadersMiddleware       │ ← Adds X-Forwarded-*
    │ (Nginx support)                  │   for reverse proxy
    └────────────────┬────────────────┘
                     │
    ┌────────────────▼────────────────┐
    │ CORSResponseMiddleware           │ ← Adds CORS headers
    │ (response headers)               │   to all responses
    └────────────────┬────────────────┘
                     │
    ┌────────────────▼────────────────┐
    │ AuthorizationHeaderMiddleware    │ ← Token relay
    │ (cookie → Authorization)         │   (cookie→header)
    └────────────────┬────────────────┘
                     │
    ┌────────────────▼────────────────┐
    │ CORSPreflightMiddleware          │ ← Handles OPTIONS!
    │ (OPTIONS → 200 OK, no proxy)     │   (CRITICAL)
    └────────────────┬────────────────┘
                     │
    ┌────────────────▼────────────────┐
    │ CORSMiddleware (FastAPI built-in)│ ← Global CORS
    │ (backup CORS handling)           │
    └────────────────┬────────────────┘
                     │
    ┌────────────────▼────────────────┐
    │ Route Handlers / Business Logic  │
    │ (gateway_routes, auth_routes)    │
    └─────────────────────────────────┘


Decision Tree (CORSPreflightMiddleware):

         ┌─ Is it an OPTIONS request?
         │  ├─ NO → let it through to next middleware
         │  └─ YES ↓
         │
         ├─ Is there an Origin header?
         │  ├─ NO → let it through to next middleware
         │  └─ YES ↓
         │
         ├─ Should proxy OPTIONS to backend?
         │  │  (checking against blacklist)
         │  ├─ YES → let it through to next middleware
         │  └─ NO ↓
         │
         ├─ Is origin allowed?
         │  │  (checking CORS_ORIGINS config)
         │  ├─ NO → return 403 Forbidden
         │  └─ YES ↓
         │
         └─ Return 200 OK with CORS headers
            (dont proxy to backend)
```

## CORS Header Flow

```
┌─────────────────────────────────────────────────┐
│ Browser Request (CORS preflight)                │
│                                                 │
│ OPTIONS /realms/.../openid-connect/auth        │
│ Origin: https://app.timesmartai.ca             │
│ Access-Control-Request-Method: POST            │
│ Access-Control-Request-Headers: Authorization │
└──────────────┬──────────────────────────────────┘
               │
               ▼
         ┌─────────────┐
         │   Gateway   │
         │             │
         │ CORSPreflight
         │ Middleware
         │ processes
         └──────┬──────┘
                │
                ▼
     ┌──────────────────────┐
     │ build_cors_headers() │
     │ (from cors.py)       │
     │                      │
     │ Builds headers:      │
     │ • Allow-Origin       │
     │ • Allow-Methods      │
     │ • Allow-Headers      │
     │ • Allow-Credentials  │
     │ • Max-Age (cache)    │
     └──────────┬───────────┘
                │
                ▼
┌──────────────────────────────────────────────────────┐
│ Gateway Response (200 OK)                            │
│                                                      │
│ HTTP/1.1 200 OK                                      │
│                                                      │
│ Access-Control-Allow-Origin:                        │
│   https://app.timesmartai.ca    ← specific origin  │
│                                                      │
│ Access-Control-Allow-Methods:                       │
│   GET, POST, PUT, DELETE, PATCH, OPTIONS, HEAD    │
│                                                      │
│ Access-Control-Allow-Headers:                       │
│   Content-Type, Authorization, X-Requested-With    │
│   Origin, Accept, ... (* means all)               │
│                                                      │
│ Access-Control-Allow-Credentials: true             │
│   ← important for OAuth2/cookies                  │
│                                                      │
│ Access-Control-Max-Age: 86400                       │
│   ← preflight cached for 24 hours                 │
│                                                      │
│ Vary: Origin                                        │
│   ← tell CDN/cache to vary by Origin              │
└──────────────┬───────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────┐
│ Browser                                         │
│                                                 │
│ ✅ CORS check passed! All headers present.      │
│                                                 │
│ Browser caches this response for 24 hours.     │
│                                                 │
│ Now allows actual request:                     │
│ POST /realms/.../openid-connect/auth           │
│ (no preflight needed for 24 hours)             │
└─────────────────────────────────────────────────┘
```

## Origin Validation Logic

```
Incoming request with Origin header:
  "Origin: https://app.timesmartai.ca"

     ↓

Check against CORS_ORIGINS config:
  [
    "https://app.timesmartai.ca",          ✓ MATCH!
    "https://idm.timesmart.io",
    "http://localhost:3000"
  ]

     ↓

Is CORS_CREDENTIALS enabled?
  ├─ YES: Return specific origin (not wildcard)
  │       "Access-Control-Allow-Origin: https://app.timesmartai.ca"
  │       "Access-Control-Allow-Credentials: true"
  │
  └─ NO: Could use wildcard
        "Access-Control-Allow-Origin: *"
        "Access-Control-Allow-Credentials: false"

     ↓

Browser receives response with correct origin
  ✅ CORS check passed!
```

## Request Timeline Comparison

### Before Fix (Broken)
```
Time 0:    Browser sends OPTIONS preflight
Time 50ms: Gateway proxies to Keycloak
Time 100ms: Keycloak returns 405 (no OPTIONS support)
Time 150ms: Gateway returns 405 to browser
Time 200ms: Browser sees CORS error, blocks request
           ❌ OAuth2 flow FAILS
```

### After Fix (Working)
```
Time 0:    Browser sends OPTIONS preflight
Time 10ms: CORSPreflightMiddleware catches it
Time 20ms: Returns 200 OK with CORS headers (no proxy!)
Time 30ms: Browser sees CORS headers, preflight PASSES
Time 40ms: Browser caches for 24 hours
Time 50ms: Browser sends actual POST request
Time 100ms: Gateway routes to /login endpoint
Time 150ms: Keycloak processes actual OAuth2 request
Time 200ms: Returns 302 redirect
           ✅ OAuth2 flow SUCCEEDS
           
Subsequent requests within 24 hours:
Time 0:    Browser sends POST (no preflight!)
Time 50ms: Gateway routes to /login
Time 100ms: Keycloak processes
           ✅ FASTER (only 1 request, not 2)
```

## Configuration Architecture

```
┌─────────────┐
│  .env file  │
└──────┬──────┘
       │
       ├─ CORS_ORIGINS=
       │  └─ https://app.timesmartai.ca,
       │     https://idm.timesmart.io      ← KEYCLOAK!
       │
       ├─ CORS_CREDENTIALS=true
       │  └─ required for OAuth2
       │
       ├─ CORS_METHODS=GET,POST,...,OPTIONS
       │  └─ must include OPTIONS
       │
       └─ KEYCLOAK_SERVER_URL=
          └─ https://idm.timesmart.io     ← Match CORS_ORIGINS!

           ↓

┌──────────────────────┐
│ app/core/cors.py     │
├──────────────────────┤
│ CORSConfig           │
│ └─ origins           │
│ └─ methods           │
│ └─ allow_headers     │
│ └─ allow_credentials │
│ └─ max_age           │
└──────────────┬───────┘
               │
               ├─ get_cors_config() → CORSConfig instance
               │
               ├─ build_cors_headers() → HTTP headers dict
               │
               └─ is_cors_request() → Check if CORS
                  get_allowed_origin() → Validate origin
                  should_proxy_options() → Don't proxy Keycloak
                  
           ↓

┌───────────────────────────────┐
│ app/filters/cors_middleware.py│
├───────────────────────────────┤
│ CORSPreflightMiddleware        │
│ └─ OPTIONS → 200 OK            │
│                                │
│ CORSResponseMiddleware         │
│ └─ Add headers to responses    │
│                                │
│ AuthorizationHeaderMiddleware  │
│ └─ Token relay (cookie→header) │
│                                │
│ ForwardedHeadersMiddleware     │
│ └─ Nginx support               │
└───────────────────────────────┘
                │
                ▼
           ┌─────────────┐
           │  Requests   │
           │  Responses  │
           └─────────────┘
```

## Environment Setup Comparison

### ❌ BROKEN (Before)
```env
CORS_ORIGINS=*
CORS_CREDENTIALS=true
# Keycloak NOT in CORS origins!
```
**Problem**: CORS_ORIGINS=* doesn't work with credentials=true
            Browser rejects OPTIONS to Keycloak

### ✅ FIXED (After)
```env
CORS_ORIGINS=https://app.timesmartai.ca,https://idm.timesmart.io
CORS_CREDENTIALS=true
# Keycloak IS in CORS origins!
```
**Success**: Specific origins with credentials support
            OPTIONS to Keycloak returns 200 OK

## Deployment Checklist

```
┌─────────────────────────────────────────────┐
│ 1. Code Changes                             │
├─────────────────────────────────────────────┤
│ ✓ app/core/cors.py (NEW)                    │
│ ✓ app/filters/cors_middleware.py (NEW)      │
│ ✓ app/main.py (middleware stack)            │
│ ✓ app/api/gateway_routes.py (docs)          │
│ ✓ app/core/config.py (validator)            │
└─────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────┐
│ 2. Configuration                            │
├─────────────────────────────────────────────┤
│ ✓ .env (CORS_ORIGINS + Keycloak)           │
│ ✓ Verify CORS_ORIGINS includes Keycloak   │
│ ✓ CORS_CREDENTIALS=true                    │
│ ✓ CORS_METHODS includes OPTIONS            │
└─────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────┐
│ 3. Build & Test                             │
├─────────────────────────────────────────────┤
│ ✓ Build Docker image                        │
│ ✓ Start container                           │
│ ✓ Check startup logs                        │
│ ✓ Test CORS preflight (curl)               │
│ ✓ Test OAuth2 flow (browser)               │
└─────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────┐
│ 4. Verification                             │
├─────────────────────────────────────────────┤
│ ✓ OPTIONS returns 200 OK                    │
│ ✓ CORS headers present                      │
│ ✓ OAuth2 login works                        │
│ ✓ Page refresh maintains session            │
│ ✓ No CORS errors in console                 │
│ ✓ X-Forwarded-* headers present             │
└─────────────────────────────────────────────┘
              ↓
         ✅ DEPLOYED!
```
