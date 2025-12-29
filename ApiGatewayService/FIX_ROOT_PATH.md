# API Gateway Fix - Root Path and Nginx Integration

## Problem
When accessing `localhost:8000/`, the gateway was returning:
```json
{
  "detail": "Route not found for /",
  "status_code": 404,
  "correlation_id": "..."
}
```

## Root Cause
1. The `determine_target_service()` function was returning `(None, None)` for unmapped paths
2. The gateway_route handler was checking `if not service_url:` which raised 404
3. No support for nginx-forwarded `/api/` prefixed paths

## Solution Applied

### 1. Fixed determine_target_service() Function
Changed from:
```python
return None, None  # ❌ This caused the 404 error
```

To:
```python
return "frontend", FRONTEND_URL  # ✅ Always return valid response
```

**Key changes:**
- Root path `/` ALWAYS routes to frontend
- All unmatched paths route to frontend (not 404)
- Function signature changed from `Optional[Tuple[str, str]]` to `Tuple[str, str]` (never returns None)

### 2. Added Support for Nginx /api/ Prefixed Paths
Added to `ROUTE_PREDICATES`:
```python
"/api/user-management-service": "user-management-service",
"/api/contract-managment-service": "contract-managment-service",
"/api/contract-management-service": "contract-management-service",
"/api/entity-service": "entity-service",
"/api/timesheet-management-service": "timesheet-management-service",
```

This allows the gateway to handle both:
- Direct paths: `/user-management-service/...`
- Nginx paths: `/api/user-management-service/...`

### 3. Removed Unnecessary 404 Check
Removed the `if not service_url:` check from gateway_route handler since service_url will NEVER be None

## How It Works Now

### Direct Access to Gateway
```
localhost:8000/
  → determine_target_service("/") 
  → returns ("frontend", "https://smmc-io-prod.timesmart.io")
  → proxies to frontend ✅
```

### Via Nginx (from your config)
```
https://timesmart.io/
  → nginx forwards to localhost:8000/
  → returns ("frontend", "https://smmc-io-prod.timesmart.io")
  → proxies to frontend ✅

https://timesmart.io/api/user-management-service/users
  → nginx forwards to localhost:8000/api/user-management-service/users
  → matches "/api/user-management-service" predicate
  → routes to ("user-management-service", "http://localhost:8001")
  → path rewritten to "/users"
  → forwards to http://localhost:8001/users ✅
```

## Service Routing Summary

| Request Path | After Routing | Forwarded To |
|-------------|---|---|
| `/` | frontend | `https://smmc-io-prod.timesmart.io/` |
| `/user-management-service/api/users` | user-management-service | `http://localhost:8001/api/users` |
| `/api/user-management-service/api/users` | user-management-service | `http://localhost:8001/api/users` |
| `/contract-managment-service/v1/contracts` | contract-managment-service | `http://localhost:8002/v1/contracts` |
| `/api/contract-managment-service/v1/contracts` | contract-managment-service | `http://localhost:8002/v1/contracts` |
| `/entity-service/api/entities` | entity-service | `http://localhost:8003/api/entities` |
| `/api/entity-service/api/entities` | entity-service | `http://localhost:8003/api/entities` |
| `/any/unmapped/path` | frontend | `https://smmc-io-prod.timesmart.io/any/unmapped/path` |

## Testing

### Test Root Path
```bash
curl http://localhost:8000/
# Should proxy to https://smmc-io-prod.timesmart.io/
```

### Test Service Routes
```bash
curl http://localhost:8000/user-management-service/api/users
# Should route to http://localhost:8001/api/users

curl http://localhost:8000/api/user-management-service/api/users
# Should also route to http://localhost:8001/api/users
```

### Test Frontend Proxy
```bash
curl http://localhost:8000/nonexistent/path
# Should proxy to https://smmc-io-prod.timesmart.io/nonexistent/path
```

## Configuration Files Modified
- `app/api/gateway_routes.py`:
  - Added `/api/` prefixed routes to `ROUTE_PREDICATES`
  - Fixed `determine_target_service()` to never return None
  - Removed unnecessary 404 check

## Notes
- The gateway now properly handles root path requests
- Works both with direct access and nginx forwarding
- Unmatched paths are gracefully forwarded to the frontend instead of returning 404
- All HTTP methods (GET, POST, PUT, PATCH, DELETE, OPTIONS, HEAD) continue to work
