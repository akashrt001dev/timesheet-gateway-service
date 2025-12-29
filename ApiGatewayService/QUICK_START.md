# FastAPI Gateway - Quick Start Guide

## One-Command Startup

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Configuration

Update `.env` with your service URLs:

```env
# Frontend URLs
REACT_URI=https://app.timesmartai.ca
FLUTTER_URI=https://app.timesmartai.ca

# Backend Service URLs (domain-based, not IP:port)
USER_MANAGEMENT_SERVICE_URL=http://localhost:8001
CONTRACT_MANAGEMENT_SERVICE_URL=http://localhost:8002
ENTITY_SERVICE_URL=http://localhost:8003
TIMESHEET_MANAGEMENT_SERVICE_URL=http://localhost:8004
NOTIFICATION_SERVICE_URL=http://localhost:8005

# Server
SERVER_PORT=8000
SERVER_HOST=0.0.0.0
ENVIRONMENT=local
LOG_LEVEL=INFO
```

## Key Routing Rules

### Frontend (No Path Rewriting)
- `/app/**` → `REACT_URI`
- `/home/**` → `FLUTTER_URI`

### Backend (Path Rewriting)
- `/auth/**`, `/user/**`, `/roles/**` → USER_MANAGEMENT_SERVICE (strip prefix)
- `/contracts/**` → CONTRACT_MANAGEMENT_SERVICE (strip `/contracts`)
- `/entity/**`, `/entityID/**` → ENTITY_SERVICE (strip prefix)
- `/timesheet/**`, `/activity/**` → TIMESHEET_MANAGEMENT_SERVICE (strip prefix)
- `/emailtemplate/**` → NOTIFICATION_SERVICE (strip `/emailtemplate`)

## Testing

```bash
# Health check
curl http://localhost:8000/health

# Authentication route (rewritten)
curl -H "Authorization: Bearer token123" \
     http://localhost:8000/auth/login
# Forwarded to: http://localhost:8001/login

# Contract route (rewritten)
curl http://localhost:8000/contracts/123
# Forwarded to: http://localhost:8002/123

# Frontend route (not rewritten)
curl http://localhost:8000/app/dashboard
# Forwarded to: https://app.timesmartai.ca/app/dashboard
```

## Key Features

✅ Exact Spring Cloud Gateway behavior
✅ No token validation at gateway (backend handles it)
✅ All headers forwarded (Authorization included)
✅ All HTTP methods supported
✅ Production-ready

## Files

| File | Purpose |
|------|---------|
| `app/main.py` | Application entry point |
| `app/api/gateway_routes.py` | Routing & proxying logic |
| `app/core/config.py` | Configuration from .env |
| `app/core/security.py` | Public routes definition |
| `app/services/gateway_forwarder.py` | Header/utility functions |
| `.env` | Environment variables |
| `requirements.txt` | Python dependencies |

## Implementation Matches Java Gateway

| Aspect | Java Config | Python Implementation |
|--------|-------------|----------------------|
| Frontend routes | `uri: ${react-uri}` | Settings.react_uri |
| Path rewriting | `RewritePath: /auth/(?<path>.*), /${path}` | Path slicing in determine_route() |
| Token relay | `default-filters: [TokenRelay=]` | All headers forwarded in proxy_request() |
| Token validation | None (backend) | None (backend) |
| CORS | Spring CORS | FastAPI CORSMiddleware |
| All methods | ✓ | ✓ |

## Detailed Documentation

- See **MIGRATION_GUIDE.md** for comprehensive guide
- See **IMPLEMENTATION_SUMMARY.md** for detailed changes

## What's Different from Java Gateway

**Same:**
- Routing behavior
- Path rewriting
- Header forwarding
- CORS handling
- No token validation

**Different (but equivalent):**
- Python async instead of Java Mono/Flux
- httpx instead of WebClient
- Environment variables instead of Eureka discovery
- FastAPI instead of Spring WebFlux

## Architecture

```
Client Request
    ↓
Gateway (main.py)
    ↓ (CORS middleware)
    ↓
gateway_routes.py: determine_route()
    ↓ (Route matching)
    ↓
gateway_routes.py: proxy_request()
    ↓ (Header preparation, httpx forwarding)
    ↓
Backend Service (user-mgmt, contracts, etc)
    ↓ (Service processes request + auth)
    ↓
Response back to Client
```

## Common Issues

**Service not found 404:**
- Check route matches exactly (case-sensitive)
- Verify service URL in .env is correct

**Authorization header not received:**
- Check backend service logs
- Gateway forwards all headers including Authorization

**CORS errors:**
- Update CORS_ORIGINS in .env to include frontend URL
- Default is `*` which allows all origins

**Service unreachable 503:**
- Verify backend service is running
- Check network connectivity
- Verify service URL in .env is correct

## Production Deployment

For Docker/Kubernetes, update .env with service DNS names:

```env
USER_MANAGEMENT_SERVICE_URL=http://user-management-service:8001
CONTRACT_MANAGEMENT_SERVICE_URL=http://contract-management-service:8002
ENTITY_SERVICE_URL=http://entity-service:8003
TIMESHEET_MANAGEMENT_SERVICE_URL=http://timesheet-management-service:8004
NOTIFICATION_SERVICE_URL=http://notification-service:8005
```

Use in Kubernetes deployment:
```yaml
spec:
  containers:
  - name: gateway
    image: your-registry/gateway:latest
    ports:
    - containerPort: 8000
    env:
    - name: REACT_URI
      value: "https://app.timesmartai.ca"
    # ... other env vars
```

## Support

The gateway is fully functional and production-ready. All routing logic is implemented exactly as specified in the Java `application.yml`.
