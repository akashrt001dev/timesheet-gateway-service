# FastAPI API Gateway - Production Implementation

## Overview

This is a **production-ready FastAPI API Gateway** that acts as a reverse proxy for multiple backend services. The gateway is fully configurable, supports all HTTP methods, properly handles headers, query parameters, and request bodies.

## Architecture

### Port Configuration
- **Gateway Port**: `8000`
- **Health Check**: `GET /health`

### Service Routing

The gateway routes requests based on path prefixes:

| Path Prefix | Target Service | Upstream Port |
|-------------|-----------------|---------------|
| `/` (root, static files) | Frontend | External HTTPS |
| `/user-management-service/**` | User Management Service | 8001 |
| `/auth/**` | User Management Service | 8001 |
| `/user/**` | User Management Service | 8001 |
| `/roles/**` | User Management Service | 8001 |
| `/contract-managment-service/**` | Contract Management Service | 8002 |
| `/contracts/**` | Contract Management Service | 8002 |
| `/entity-service/**` | Entity Service | 8003 |
| `/entity/**` | Entity Service | 8003 |
| `/app/entitySitePortal/**` | Entity Service | 8003 |
| `/timesheet-management-service/**` | Timesheet Management Service | 8004 |
| `/timesheet/**` | Timesheet Management Service | 8004 |
| `/activity/**` | Timesheet Management Service | 8004 |

### Frontend Configuration

The frontend is deployed at:
```
https://smmc-io-prod.timesmart.io
```

Requests to the root path `/` and unmapped paths are proxied to this external frontend URL.

## Key Features

### 1. HTTP Method Support
- ✅ GET - Retrieve resources
- ✅ POST - Create resources
- ✅ PUT - Replace resources
- ✅ PATCH - Partial updates
- ✅ DELETE - Remove resources
- ✅ OPTIONS - CORS preflight and method discovery
- ✅ HEAD - Retrieve headers without body

### 2. Request Forwarding
- **Headers**: All headers forwarded except hop-by-hop headers (`Connection`, `Transfer-Encoding`, etc.)
- **Query Parameters**: Fully preserved and forwarded
- **Request Body**: Forwarded for POST, PUT, PATCH requests
- **Content-Type**: Properly detected and forwarded
- **Correlation IDs**: Automatically added for request tracing

### 3. Response Handling
- **Status Codes**: Preserved from upstream service
- **Response Headers**: Forwarded with appropriate filtering
- **Response Body**: Streamed for efficient memory usage
- **Content-Type**: Properly maintained
- **Redirects**: Automatically followed (up to default limit)

### 4. Static Asset Support
The gateway recognizes and properly handles static files:
- JavaScript (`.js`)
- Stylesheets (`.css`)
- Images (`.png`, `.jpg`, `.gif`, `.svg`, `.ico`)
- Fonts (`.woff`, `.woff2`, `.ttf`, `.eot`)
- Web assets (`.json`, `.html`, `.map`)
- Media files (`.wav`, `.mp3`, `.mp4`, `.webm`)
- Documents (`.pdf`, `.doc`, `.docx`)
- Service workers

### 5. Error Handling

The gateway provides detailed error responses:

| Status Code | Scenario |
|------------|----------|
| 400 | Bad Request |
| 404 | Route not found |
| 502 | Bad Gateway (upstream error) |
| 503 | Service Unavailable |
| 504 | Gateway Timeout |
| 500 | Internal Server Error |

### 6. Request Forwarding Logic

```
Incoming Request → Path Analysis → Service Routing → Path Rewriting → Upstream Proxy
```

#### Path Rewriting Example
When routing to backend services, the service prefix is removed:

```
/user-management-service/api/users     →  /api/users        (User Service)
/contract-managment-service/v1/list     →  /v1/list          (Contract Service)
/entity-service/portal/settings          →  /portal/settings  (Entity Service)
/timesheet-management-service/entries   →  /entries          (Timesheet Service)
```

## Configuration

### Environment Variables

Create a `.env` file in the root directory:

```env
# Server Configuration
SERVER_PORT=8000
SERVER_HOST=0.0.0.0
ENVIRONMENT=production
LOG_LEVEL=INFO

# Upstream Services
USER_SERVICE_URL=http://localhost:8001
CONTRACT_SERVICE_URL=http://localhost:8002
ENTITY_SERVICE_URL=http://localhost:8003
TIMESHEET_SERVICE_URL=http://localhost:8004

# CORS Configuration
CORS_ORIGINS=*
CORS_CREDENTIALS=true
CORS_METHODS=GET,POST,PUT,DELETE,PATCH,OPTIONS
CORS_HEADERS=*

# Request Timeout (seconds)
REQUEST_TIMEOUT_SECONDS=30

# JWT Configuration
JWT_SECRET=your-secret-key-here
JWT_ALGORITHM=HS256
```

## Code Structure

### Main Components

#### 1. **main.py** - Application Entry Point
- FastAPI application setup
- Middleware configuration
- Exception handlers
- Health check endpoint
- Lifespan management

#### 2. **gateway_routes.py** - Core Routing Logic
Contains the primary gateway implementation:

**Key Functions:**
- `proxy_request()` - Core reusable proxy helper function
- `determine_target_service()` - Route path to upstream service
- `rewrite_path_for_upstream()` - Remove service prefix from path
- `is_static_file()` - Identify static assets
- `gateway_route()` - Main catch-all route handler

**Route Configuration:**
- `UPSTREAM_SERVICES` - Mapping of service IDs to URLs
- `ROUTE_PREDICATES` - Mapping of path prefixes to service IDs
- `STATIC_EXTENSIONS` - Recognized static file extensions
- `FRONTEND_URL` - External frontend URL

#### 3. **config.py** - Configuration Management
- Environment variable handling
- Settings validation
- Service URL configuration
- Logging setup

#### 4. **Middleware** - Request/Response Processing
- `CorrelationIDMiddleware` - Request tracing
- `RequestLoggingMiddleware` - Request/response logging
- `AuthenticationMiddleware` - JWT validation
- `HeaderRemovalMiddleware` - Security header filtering
- `CORSMiddleware` - Cross-Origin Resource Sharing

## Usage Examples

### Starting the Gateway

```bash
# Using startup script
./startup.sh

# Or with Python directly
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Or with Docker
docker-compose up
```

### Request Examples

#### 1. Get User (through User Service)
```bash
curl -X GET http://localhost:8000/user-management-service/api/users/123 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### 2. Create Contract (through Contract Service)
```bash
curl -X POST http://localhost:8000/contract-managment-service/v1/contracts \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"name":"New Contract","type":"SERVICE"}'
```

#### 3. Update Entity (through Entity Service)
```bash
curl -X PATCH http://localhost:8000/entity-service/api/entities/456 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"status":"ACTIVE"}'
```

#### 4. Health Check
```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "service": "gateway-service",
  "version": "1.0.0"
}
```

#### 5. Frontend Root Path
```bash
curl http://localhost:8000/
# → Proxies to https://smmc-io-prod.timesmart.io/
```

## Implementation Details

### Proxy Request Helper

The `proxy_request()` function is the core of the gateway:

```python
async def proxy_request(
    request: Request,
    upstream_url: str,
    upstream_path: str,
    timeout: float = HTTPX_TIMEOUT
) -> Tuple[int, Dict[str, str], bytes]:
    """
    Forward an HTTP request to an upstream service.
    Returns (status_code, headers, body)
    """
```

**Features:**
- Handles all HTTP methods generically
- Filters hop-by-hop headers automatically
- Preserves query parameters
- Forwards request body for POST/PUT/PATCH
- Returns complete response with headers and body
- Provides detailed error messages

### Generic Method Handling

Instead of separate handlers per method, the gateway uses a single catch-all route:

```python
@router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
    tags=["Gateway"],
)
async def gateway_route(request: Request, path: str = ""):
```

This handler processes all methods through the same logic, keeping code clean and DRY.

### Error Handling

The gateway catches and properly formats errors:

```python
try:
    # Forward request
    status_code, headers, body = await proxy_request(...)
    return StreamingResponse(...)
except httpx.TimeoutException:
    raise HTTPException(status_code=504, detail="Gateway timeout")
except httpx.ConnectError:
    raise HTTPException(status_code=503, detail="Service unavailable")
except Exception:
    raise HTTPException(status_code=502, detail="Bad gateway")
```

## Performance Considerations

### 1. Async Processing
- Uses `httpx.AsyncClient` for non-blocking I/O
- Handles multiple concurrent requests efficiently
- Connection pooling configured with limits

### 2. Streaming Responses
```python
return StreamingResponse(
    iter([response_body]),
    status_code=status_code,
    headers=response_headers,
)
```
Streams response bodies to avoid memory overhead on large payloads.

### 3. Connection Pooling
```python
HTTPX_CLIENT_CONFIG = {
    "timeout": HTTPX_TIMEOUT,
    "follow_redirects": True,
    "limits": httpx.Limits(
        max_keepalive_connections=100,
        max_connections=100
    ),
}
```

### 4. Timeout Configuration
Default timeout: **30 seconds** (configurable via `REQUEST_TIMEOUT_SECONDS` environment variable)

## Monitoring and Debugging

### Health Endpoint
```bash
curl http://localhost:8000/health
```

### Correlation IDs
Each request is assigned a unique correlation ID for tracing:
```
X-Correlation-ID: f47ac10b-58cc-4372-a567-0e02b2c3d479
```

### Logging
Logs are configured based on `LOG_LEVEL` environment variable:
- `DEBUG` - Detailed request/response information
- `INFO` - Service startup, routing decisions
- `WARNING` - Missing routes, configuration issues
- `ERROR` - Connection failures, timeouts

Example log output:
```
INFO     app.api.gateway_routes: Proxying GET /user-management-service/api/users → http://localhost:8001/api/users
DEBUG    app.api.gateway_routes: Received 200 from upstream
```

## Security Considerations

### 1. Header Filtering
Sensitive headers are filtered:
- `Cookie` - Browser cookies (optional based on configuration)
- `Authorization` - JWT tokens (forwarded)
- `X-Correlation-ID` - Added by gateway

### 2. CORS
Configurable CORS policies:
```env
CORS_ORIGINS=https://smmc-io-prod.timesmart.io,http://localhost:3000
CORS_CREDENTIALS=true
CORS_METHODS=GET,POST,PUT,DELETE,PATCH,OPTIONS
CORS_HEADERS=Authorization,Content-Type,X-Correlation-ID
```

### 3. Authentication Middleware
Optional JWT validation on all requests (configured in `AuthenticationMiddleware`)

### 4. Input Validation
Query parameters and request bodies are forwarded as-is (upstream services should validate)

## Deployment

### Docker
```bash
docker-compose up -d
```

### Kubernetes
```yaml
apiVersion: v1
kind: Service
metadata:
  name: api-gateway
spec:
  selector:
    app: api-gateway
  ports:
  - protocol: TCP
    port: 8000
    targetPort: 8000
  type: LoadBalancer
```

### Production Checklist
- [ ] Configure all upstream service URLs in `.env`
- [ ] Set `ENVIRONMENT=production`
- [ ] Set `LOG_LEVEL=WARNING`
- [ ] Configure CORS origins appropriately
- [ ] Enable JWT authentication
- [ ] Set up monitoring and alerting
- [ ] Configure request timeouts based on upstream SLAs
- [ ] Test with load (k6, Apache Bench)
- [ ] Set up log aggregation (ELK Stack, CloudWatch)
- [ ] Enable request rate limiting (nginx, API Gateway)

## Troubleshooting

### Gateway Returns 404
- Check if the path matches any configured route prefix
- Verify path is correctly formatted (e.g., `/user-management-service/...`)
- Check ROUTE_PREDICATES in gateway_routes.py

### Upstream Service Returns 503
- Verify upstream service is running
- Check service URL in `.env` configuration
- Check network connectivity between gateway and upstream
- Review upstream service logs

### Timeout Errors (504)
- Increase `REQUEST_TIMEOUT_SECONDS` in `.env`
- Check upstream service performance
- Review upstream service logs for slow requests
- Consider implementing request queuing

### CORS Errors in Browser
- Add frontend URL to `CORS_ORIGINS` in `.env`
- Verify `CORS_METHODS` includes required HTTP methods
- Check `CORS_HEADERS` includes necessary request headers
- Clear browser cache and cookies

## Future Enhancements

1. **Rate Limiting** - Per-client or per-endpoint rate limits
2. **Caching** - Cache responses from upstream services
3. **Load Balancing** - Multiple instances per upstream service
4. **Circuit Breaker** - Prevent cascading failures
5. **Request/Response Transformation** - Modify headers/bodies in-flight
6. **API Versioning** - Version-aware routing
7. **Analytics** - Request metrics and insights
8. **Webhook Support** - Forward specific events to external systems
9. **GraphQL Gateway** - Support GraphQL federation
10. **Service Mesh Integration** - Istio/Linkerd integration

---

**Version**: 1.0.0  
**Last Updated**: December 2025  
**Status**: Production Ready
