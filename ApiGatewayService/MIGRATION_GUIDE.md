# FastAPI Gateway Migration - Spring Cloud Gateway Equivalent

## Overview

This FastAPI gateway is a production-ready equivalent of the Java Spring Cloud Gateway configured in `application.yml`.

It implements:
- **Exact routing behavior** from the Java Gateway
- **Path rewriting** matching Spring's `RewritePath` filters
- **TokenRelay**: Forward Authorization and all headers to backend services
- **NO token validation** at gateway level (backend services handle auth)
- **All HTTP methods** supported (GET, POST, PUT, DELETE, PATCH, OPTIONS, HEAD)

## Architecture

### Components

```
main.py                    # Application entry point, CORS, exception handling
├── config.py             # Settings from .env (maps to application.yml)
├── security.py           # Public routes definition (no token validation)
└── api/
    └── gateway_routes.py # Routing logic with path rewriting
```

### Request Flow

1. **Incoming Request** → FastAPI endpoint `gateway_route()`
2. **Route Determination** → `GatewayRouter.determine_route()` maps path to service
3. **Path Rewriting** → Strip prefix matching Spring `RewritePath` filters
4. **Header Forwarding** → All headers forwarded including `Authorization` (TokenRelay)
5. **Request Proxying** → `proxy_request()` forwards to upstream service
6. **Response Return** → Response from upstream returned to client

## Running the Gateway

### One Command Startup

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Or with reload for development:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Requirements

All Python dependencies are in `requirements.txt`:
- FastAPI 0.104.1
- Uvicorn 0.24.0  
- Pydantic 2.5.0
- httpx 0.25.1
- python-dotenv 1.0.0

Install with:
```bash
pip install -r requirements.txt
```

## Configuration (.env)

All configuration uses environment variables (matching Spring `application.yml`):

### Frontend URLs
```env
REACT_URI=https://app.timesmartai.ca
FLUTTER_URI=https://app.timesmartai.ca
```

### Backend Service URLs (Domain-based, not IP:port)
```env
USER_MANAGEMENT_SERVICE_URL=http://localhost:8001
CONTRACT_MANAGEMENT_SERVICE_URL=http://localhost:8002
ENTITY_SERVICE_URL=http://localhost:8003
TIMESHEET_MANAGEMENT_SERVICE_URL=http://localhost:8004
NOTIFICATION_SERVICE_URL=http://localhost:8005
```

### Server Configuration
```env
SERVER_PORT=8000
SERVER_HOST=0.0.0.0
ENVIRONMENT=local
LOG_LEVEL=INFO
```

### CORS Configuration
```env
CORS_ORIGINS=*
CORS_CREDENTIALS=true
CORS_METHODS=GET,POST,PUT,DELETE,OPTIONS,PATCH,HEAD
CORS_HEADERS=*
```

## Routing Rules

Exactly matching `application.yml` from the Java Gateway:

### Frontend Routes (No Rewriting)

| Path | Target | Rewriting |
|------|--------|-----------|
| `/app/**` | `react-uri` | None (path preserved) |
| `/home/**` | `flutter-uri` | None (path preserved) |

### Backend Routes (With Path Rewriting)

#### User Management Service
```
/auth/**  → user-management-service → strip /auth
/user/**  → user-management-service → strip /user  
/roles/** → user-management-service → strip /roles
```

Example:
- Request: `POST /auth/login`
- Forwarded: `POST http://user-management-service:8001/login`

#### Contract Management Service
```
/contracts/** → contract-management-service → strip /contracts
```

Example:
- Request: `GET /contracts/123`
- Forwarded: `GET http://contract-management-service:8002/123`

#### Entity Service
```
/entity/**   → entity-service → strip /entity
/entityID/** → entity-service → strip /entityID
```

Example:
- Request: `GET /entity/ACME/logo`
- Forwarded: `GET http://entity-service:8003/ACME/logo`

#### Timesheet Management Service
```
/timesheet/** → timesheet-management-service → strip /timesheet
/activity/**  → timesheet-management-service → strip /activity
```

Examples:
- Request: `POST /timesheet/123`
- Forwarded: `POST http://timesheet-management-service:8004/123`

- Request: `POST /activity/track`
- Forwarded: `POST http://timesheet-management-service:8004/track`

#### Notification Service
```
/emailtemplate/** → notification-service → strip /emailtemplate
```

Example:
- Request: `GET /emailtemplate/welcome`
- Forwarded: `GET http://notification-service:8005/welcome`

## Security Model

### NO Token Validation at Gateway

The gateway **deliberately does NOT validate JWT tokens**. This matches Spring Cloud Gateway's design:
- Gateway forwards all requests
- Backend services validate tokens
- Backend services enforce authorization

### TokenRelay Implementation

The gateway forwards **ALL headers** including `Authorization`:

```python
# All headers forwarded except hop-by-hop
forward_headers: Dict[str, str] = {}
for header_name, header_value in request.headers.items():
    if header_name.lower() not in HOP_BY_HOP_HEADERS:
        forward_headers[header_name] = header_value
```

### Public Routes

These routes are marked as "public" but still proxied - backend services may enforce auth:
- `/login/**`
- `/oauth2/**`
- `/app/**`
- `/home/**`
- `/v3/api-docs/**`
- etc.

The gateway simply doesn't check these; it forwards the request to the appropriate backend.

## Key Implementation Details

### Path Rewriting Logic

Implements Spring Cloud Gateway's `RewritePath` filters:

```python
def determine_route(self, path: str):
    # For path /auth/login with prefix /auth
    # Remove the prefix: /auth/login → /login
    if path.startswith(prefix):
        rewritten = path[len(strip_prefix):]
        if not rewritten.startswith("/"):
            rewritten = "/" + rewritten
```

### Async HTTP Client

Uses `httpx.AsyncClient` for non-blocking proxying:
- Maintains connection pool (100 max)
- Follows redirects automatically
- 30-second timeout by default
- Preserves query parameters
- Handles all HTTP methods

### Header Management

Removes hop-by-hop headers per HTTP specification:
- `connection`, `keep-alive`, `proxy-authenticate`, etc.
- Preserves user headers
- Preserves `Authorization` header (TokenRelay)
- Adds `X-Correlation-ID` for tracing

### Error Handling

- **404**: No matching route
- **503**: Cannot reach upstream service
- **504**: Upstream timeout
- **502**: Error forwarding request
- **500**: Internal server error

## Development

### Adding a New Service Route

To add routing for a new service in `app/api/gateway_routes.py`:

1. Add service URL to `.env`:
   ```env
   MY_SERVICE_URL=http://localhost:8006
   ```

2. Add to `Settings` class in `app/core/config.py`:
   ```python
   my_service_url: str = Field(
       default="http://localhost:8006",
       alias="MY_SERVICE_URL",
       description="My new service"
   )
   ```

3. Add route to `GatewayRouter` in `app/api/gateway_routes.py`:
   ```python
   self.backend_routes = {
       # ... existing routes ...
       "/myservice": (settings.my_service_url, "/myservice"),
   }
   ```

### Testing

Test the gateway with curl:

```bash
# Frontend routing (no rewriting)
curl http://localhost:8000/app/

# Backend routing (with rewriting)
curl -H "Authorization: Bearer token123" \
     http://localhost:8000/auth/login

# Should be forwarded as: POST http://user-management-service:8001/login
```

### Logging

Configure log level in `.env`:
```env
LOG_LEVEL=INFO
```

Available levels: DEBUG, INFO, WARNING, ERROR, CRITICAL

Logs include:
- Route determination
- Request proxying
- Upstream responses
- Errors and exceptions

## Comparison with Java Gateway

| Feature | Java Gateway | Python Gateway |
|---------|--------------|----------------|
| Frontend routing | ✓ | ✓ |
| Path rewriting | Spring RewritePath | Python string slicing |
| TokenRelay | default-filters | Explicit header forwarding |
| Token validation | None (backend) | None (backend) |
| CORS | CORSMiddleware | FastAPI CORSMiddleware |
| Async handling | Mono/Flux | AsyncClient |
| Service discovery | Eureka/lb:// | Environment variables |

## Production Deployment

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Variables for Production

```env
ENVIRONMENT=production
LOG_LEVEL=INFO

REACT_URI=https://app.timesmartai.ca
FLUTTER_URI=https://app.timesmartai.ca

USER_MANAGEMENT_SERVICE_URL=http://user-service:8001
CONTRACT_MANAGEMENT_SERVICE_URL=http://contract-service:8002
ENTITY_SERVICE_URL=http://entity-service:8003
TIMESHEET_MANAGEMENT_SERVICE_URL=http://timesheet-service:8004
NOTIFICATION_SERVICE_URL=http://notification-service:8005

CORS_ORIGINS=https://app.timesmartai.ca,https://api.timesmartai.ca
```

### Kubernetes

Use service discovery with DNS:
```env
USER_MANAGEMENT_SERVICE_URL=http://user-management-service.default.svc.cluster.local:8001
```

## Troubleshooting

### Gateway not reaching services

Check that service URLs in `.env` are correct and services are running:
```bash
curl http://localhost:8001/health  # Check if service is up
```

### CORS errors

Verify `CORS_ORIGINS` includes the frontend URL:
```env
CORS_ORIGINS=https://app.timesmartai.ca,http://localhost:3000
```

### Authorization header not forwarded

The gateway should forward all headers. Check that:
- No middleware is removing it
- Backend service expects the header

### Paths not rewriting correctly

Verify the path prefix matches exactly. Request `/auth/login` matches `/auth` prefix.

## Migration Notes

### Removed Components

The following were removed as they're not needed in a gateway without token validation:
- `JwtUtil` class (JWT token validation)
- `RouterValidator` class (route security checking)
- `AuthenticationMiddleware` (token validation)
- Eureka client (using env vars instead)

### Simplified Dependencies

Removed:
- `PyJWT` (no token validation)
- Complex route configuration classes

## Performance Considerations

- Connection pooling: 100 max connections
- Request timeout: 30 seconds (configurable)
- Async I/O: Non-blocking request handling
- Streaming responses: Large payloads handled efficiently

## Health Check

The gateway exposes a health endpoint:

```
GET /health
```

Response:
```json
{
  "status": "healthy",
  "service": "api-gateway-service",
  "version": "1.0.0"
}
```

Use for Kubernetes liveness/readiness probes.
