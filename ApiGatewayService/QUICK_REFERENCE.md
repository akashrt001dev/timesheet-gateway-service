# Quick Reference - API Gateway

## 🚀 Quick Start (2 minutes)

```bash
# 1. Install
pip install -r requirements.txt

# 2. Create .env
cat > .env << EOF
SERVER_PORT=8000
ENVIRONMENT=local
LOG_LEVEL=DEBUG

USER_SERVICE_URL=http://localhost:8001
CONTRACT_SERVICE_URL=http://localhost:8002
ENTITY_SERVICE_URL=http://localhost:8003
TIMESHEET_SERVICE_URL=http://localhost:8004

CORS_ORIGINS=*
EOF

# 3. Run
python -m uvicorn app.main:app --reload

# 4. Test
curl http://localhost:8000/health
```

## 📋 Common Commands

### Health Check
```bash
curl http://localhost:8000/health
```

### User Service
```bash
# List users
curl http://localhost:8000/user-management-service/api/users

# Create user
curl -X POST http://localhost:8000/user-management-service/api/users \
  -H "Content-Type: application/json" \
  -d '{"username":"john","email":"john@example.com"}'

# Get user
curl http://localhost:8000/user-management-service/api/users/1

# Update user
curl -X PUT http://localhost:8000/user-management-service/api/users/1 \
  -H "Content-Type: application/json" \
  -d '{"email":"john.new@example.com"}'

# Delete user
curl -X DELETE http://localhost:8000/user-management-service/api/users/1

# Login
curl http://localhost:8000/auth/login
```

### Contract Service
```bash
# List contracts
curl http://localhost:8000/contract-managment-service/v1/contracts

# Create contract
curl -X POST http://localhost:8000/contract-managment-service/v1/contracts \
  -H "Content-Type: application/json" \
  -d '{"name":"Contract A","type":"SERVICE"}'

# Get contract
curl http://localhost:8000/contract-managment-service/v1/contracts/123

# List all contracts (via alternate path)
curl http://localhost:8000/contracts
```

### Entity Service
```bash
# List entities
curl http://localhost:8000/entity-service/api/entities

# Create entity
curl -X POST http://localhost:8000/entity-service/api/entities \
  -H "Content-Type: application/json" \
  -d '{"name":"ACME Corp","type":"COMPANY"}'

# Search entities
curl http://localhost:8000/entity/search?name=ACME
```

### Timesheet Service
```bash
# List timesheets
curl http://localhost:8000/timesheet-management-service/api/timesheets

# Create timesheet entry
curl -X POST http://localhost:8000/timesheet-management-service/api/entries \
  -H "Content-Type: application/json" \
  -d '{"userId":"user123","hours":8,"date":"2025-01-15"}'

# Get user timesheets
curl http://localhost:8000/timesheet/user/123

# Log activity
curl -X POST http://localhost:8000/activity/log \
  -H "Content-Type: application/json" \
  -d '{"userId":"user123","action":"LOGIN"}'
```

### Frontend
```bash
# Root path (proxies to external frontend)
curl http://localhost:8000/

# Static files
curl http://localhost:8000/styles.css
curl http://localhost:8000/main.js
curl http://localhost:8000/service-worker.js
```

## 🔧 Configuration Quick Map

| Variable | Purpose | Default | Example |
|----------|---------|---------|---------|
| `SERVER_PORT` | Gateway port | 8000 | 8000 |
| `SERVER_HOST` | Bind address | 0.0.0.0 | 0.0.0.0 |
| `ENVIRONMENT` | Environment | local | local/staging/production |
| `LOG_LEVEL` | Log verbosity | INFO | DEBUG/INFO/WARNING/ERROR |
| `USER_SERVICE_URL` | User service URL | http://localhost:8001 | http://localhost:8001 |
| `CONTRACT_SERVICE_URL` | Contract service | http://localhost:8002 | http://localhost:8002 |
| `ENTITY_SERVICE_URL` | Entity service | http://localhost:8003 | http://localhost:8003 |
| `TIMESHEET_SERVICE_URL` | Timesheet service | http://localhost:8004 | http://localhost:8004 |
| `CORS_ORIGINS` | Allowed origins | * | https://timesmart.io |
| `CORS_METHODS` | Allowed methods | * | GET,POST,PUT,DELETE |
| `REQUEST_TIMEOUT_SECONDS` | Request timeout | 30 | 30 |
| `JWT_SECRET` | JWT secret | (dev key) | your-secret-key |
| `JWT_ALGORITHM` | JWT algorithm | HS256 | HS256 |

## 🛣️ Route Summary

| Request Path | Forwards To | Service |
|-------------|-------------|---------|
| `/user-management-service/*` | http://localhost:8001 | User Service |
| `/auth/*` | http://localhost:8001 | User Service |
| `/user/*` | http://localhost:8001 | User Service |
| `/roles/*` | http://localhost:8001 | User Service |
| `/contract-managment-service/*` | http://localhost:8002 | Contract Service |
| `/contracts/*` | http://localhost:8002 | Contract Service |
| `/entity-service/*` | http://localhost:8003 | Entity Service |
| `/entity/*` | http://localhost:8003 | Entity Service |
| `/app/entitySitePortal/*` | http://localhost:8003 | Entity Service |
| `/timesheet-management-service/*` | http://localhost:8004 | Timesheet Service |
| `/timesheet/*` | http://localhost:8004 | Timesheet Service |
| `/activity/*` | http://localhost:8004 | Timesheet Service |
| `/` | https://smmc-io-prod.timesmart.io | Frontend |

## 🐛 Debugging

### Enable Debug Logging
```bash
LOG_LEVEL=DEBUG python -m uvicorn app.main:app --reload
```

### Check Correlation IDs
```bash
curl -v http://localhost:8000/user-management-service/api/users 2>&1 | grep -i x-correlation
```

### Test Upstream Service Connection
```bash
# User Service
curl http://localhost:8001/api/users

# Contract Service
curl http://localhost:8002/v1/contracts

# Entity Service
curl http://localhost:8003/api/entities

# Timesheet Service
curl http://localhost:8004/api/timesheets
```

### Check Gateway Logs
```bash
# Running in foreground shows logs
python -m uvicorn app.main:app

# Or check if running in background
tail -f gateway.log
```

## 📊 Monitoring

### Health Status
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

### Performance Check
```bash
# Measure response time
curl -w "\nTime: %{time_total}s\n" http://localhost:8000/health
```

### Load Testing
```bash
# Using parallel
parallel -j 10 'curl http://localhost:8000/health' ::: $(seq 1 100)

# Using Apache Bench (if installed)
ab -n 1000 -c 10 http://localhost:8000/health
```

## 🐳 Docker Quick Commands

### Build Docker Image
```bash
docker build -t api-gateway:1.0 .
```

### Run Container
```bash
docker run -p 8000:8000 \
  -e USER_SERVICE_URL=http://localhost:8001 \
  -e CONTRACT_SERVICE_URL=http://localhost:8002 \
  -e ENTITY_SERVICE_URL=http://localhost:8003 \
  -e TIMESHEET_SERVICE_URL=http://localhost:8004 \
  api-gateway:1.0
```

### Docker Compose
```bash
docker-compose up -d
```

## 📁 File Quick Reference

| File | Purpose |
|------|---------|
| `app/main.py` | FastAPI app setup, middleware |
| `app/api/gateway_routes.py` | **Core gateway logic** |
| `app/core/config.py` | Configuration & settings |
| `app/filters/middleware.py` | Request/response middleware |
| `.env` | Environment variables |
| `requirements.txt` | Python dependencies |
| `GATEWAY_IMPLEMENTATION.md` | **Complete guide** |
| `TESTING_GUIDE.md` | **Testing examples** |
| `CONFIG_EXAMPLES.md` | **Configuration examples** |
| `ARCHITECTURE.md` | **System design** |

## 🚨 Common Issues

### Issue: 404 Not Found
**Solution**: Verify path matches a service prefix
```bash
# ✓ Correct paths
curl http://localhost:8000/user-management-service/api/users
curl http://localhost:8000/contract-managment-service/v1/contracts

# ✗ Incorrect paths
curl http://localhost:8000/api/users  # Missing service prefix
```

### Issue: 503 Service Unavailable
**Solution**: Upstream service not running
```bash
# Check if upstream is running
netstat -an | grep 8001
netstat -an | grep 8002
netstat -an | grep 8003
netstat -an | grep 8004

# Start test service
python -m uvicorn test_service:app --port 8001
```

### Issue: 504 Gateway Timeout
**Solution**: Increase timeout or fix upstream service performance
```bash
# Increase timeout
REQUEST_TIMEOUT_SECONDS=60 python -m uvicorn app.main:app
```

### Issue: CORS Error in Browser
**Solution**: Add origin to CORS_ORIGINS
```bash
# In .env
CORS_ORIGINS=https://smmc-io-prod.timesmart.io,http://localhost:3000
```

## 📚 Key Code Locations

### Proxy Helper Function
**File**: [app/api/gateway_routes.py](app/api/gateway_routes.py#L156-L240)

Core reusable function that handles all HTTP methods:
```python
async def proxy_request(
    request: Request,
    upstream_url: str,
    upstream_path: str,
    timeout: float = HTTPX_TIMEOUT
) -> Tuple[int, Dict[str, str], bytes]:
```

### Route Determination
**File**: [app/api/gateway_routes.py](app/api/gateway_routes.py#L97-L130)

Maps path to upstream service:
```python
def determine_target_service(path: str) -> Optional[Tuple[str, str]]:
```

### Path Rewriting
**File**: [app/api/gateway_routes.py](app/api/gateway_routes.py#L133-L167)

Removes service prefix before forwarding:
```python
def rewrite_path_for_upstream(path: str, service_id: str) -> str:
```

### Main Route Handler
**File**: [app/api/gateway_routes.py](app/api/gateway_routes.py#L243-L357)

Single handler for all methods and paths:
```python
@router.api_route("/{path:path}", methods=[...])
async def gateway_route(request: Request, path: str = ""):
```

## 🎯 Typical Flow Example

```
Client Request:
POST /user-management-service/api/users
Content-Type: application/json
{"username":"john","email":"john@example.com"}

↓ Gateway:

1. determine_target_service("/user-management-service/api/users")
   → Returns ("user-management-service", "http://localhost:8001")

2. rewrite_path_for_upstream("/user-management-service/api/users", "user-management-service")
   → Returns "/api/users"

3. proxy_request(
     request=incoming_request,
     upstream_url="http://localhost:8001",
     upstream_path="/api/users"
   )
   → Forwards POST to http://localhost:8001/api/users with body

4. Upstream Service Response:
   201 Created
   {"id":1,"username":"john","email":"john@example.com"}

↓ Client Response:

201 Created
{"id":1,"username":"john","email":"john@example.com"}
```

## 📞 Support Resources

- **Implementation Details** → GATEWAY_IMPLEMENTATION.md
- **Testing Guide** → TESTING_GUIDE.md
- **Configuration** → CONFIG_EXAMPLES.md
- **Architecture** → ARCHITECTURE.md
- **This Document** → QUICK_REFERENCE.md

---

**Last Updated**: December 2025  
**Version**: 1.0.0
