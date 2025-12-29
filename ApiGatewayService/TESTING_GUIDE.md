# FastAPI Gateway - Testing and Examples

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Create `.env` file:
```env
SERVER_PORT=8000
SERVER_HOST=0.0.0.0
ENVIRONMENT=local
LOG_LEVEL=DEBUG

# Upstream Services
USER_SERVICE_URL=http://localhost:8001
CONTRACT_SERVICE_URL=http://localhost:8002
ENTITY_SERVICE_URL=http://localhost:8003
TIMESHEET_SERVICE_URL=http://localhost:8004

# CORS
CORS_ORIGINS=*
CORS_CREDENTIALS=true
CORS_METHODS=GET,POST,PUT,DELETE,PATCH,OPTIONS
CORS_HEADERS=*

# Timeouts
REQUEST_TIMEOUT_SECONDS=30

# JWT
JWT_SECRET=dev-secret-key-not-for-production
JWT_ALGORITHM=HS256
```

### 3. Start the Gateway
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Expected output:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

## Testing the Gateway

### Health Check
```bash
curl -i http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "service": "gateway-service",
  "version": "1.0.0"
}
```

### Test User Service Routing

#### Create User
```bash
curl -X POST http://localhost:8000/user-management-service/api/users \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "firstName": "Test",
    "lastName": "User"
  }'
```

#### Get User
```bash
curl -X GET "http://localhost:8000/user-management-service/api/users/1"
```

#### Get All Users
```bash
curl -X GET "http://localhost:8000/user-management-service/api/users?page=0&size=10"
```

#### Update User
```bash
curl -X PUT http://localhost:8000/user-management-service/api/users/1 \
  -H "Content-Type: application/json" \
  -d '{
    "email": "newemail@example.com",
    "firstName": "Updated"
  }'
```

#### Delete User
```bash
curl -X DELETE http://localhost:8000/user-management-service/api/users/1
```

### Test Contract Service Routing

#### Create Contract
```bash
curl -X POST http://localhost:8000/contract-managment-service/v1/contracts \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Service Agreement",
    "type": "SERVICE",
    "status": "DRAFT",
    "startDate": "2025-01-01",
    "endDate": "2025-12-31"
  }'
```

#### List Contracts
```bash
curl -X GET "http://localhost:8000/contracts?status=ACTIVE&limit=20"
```

#### Get Contract Details
```bash
curl -X GET http://localhost:8000/contract-managment-service/v1/contracts/123
```

### Test Entity Service Routing

#### Create Entity
```bash
curl -X POST http://localhost:8000/entity-service/api/entities \
  -H "Content-Type: application/json" \
  -d '{
    "name": "ACME Corp",
    "type": "COMPANY",
    "status": "ACTIVE"
  }'
```

#### Query Entities
```bash
curl -X GET "http://localhost:8000/entity/search?name=ACME&type=COMPANY"
```

### Test Timesheet Service Routing

#### Create Timesheet Entry
```bash
curl -X POST http://localhost:8000/timesheet-management-service/api/entries \
  -H "Content-Type: application/json" \
  -d '{
    "userId": "user123",
    "date": "2025-01-15",
    "hours": 8.0,
    "description": "Regular work"
  }'
```

#### Get Timesheet
```bash
curl -X GET "http://localhost:8000/timesheet/user/user123?month=2025-01"
```

#### Log Activity
```bash
curl -X POST http://localhost:8000/activity/log \
  -H "Content-Type: application/json" \
  -d '{
    "userId": "user123",
    "action": "LOGIN",
    "timestamp": "2025-01-15T10:30:00Z"
  }'
```

### Test Root Path (Frontend)
```bash
curl -i http://localhost:8000/
# Should proxy to https://smmc-io-prod.timesmart.io/
```

### Test Static Files
```bash
# JavaScript
curl -i http://localhost:8000/main.js

# CSS
curl -i http://localhost:8000/styles.css

# Service Worker
curl -i http://localhost:8000/service-worker.js
```

## Advanced Testing

### Using httpie (Better than curl)
```bash
# Install
pip install httpie

# Create user with formatted output
http POST localhost:8000/user-management-service/api/users \
  username=testuser \
  email=test@example.com

# Get with headers
http -v GET localhost:8000/user-management-service/api/users/1

# File upload
http -f POST localhost:8000/entity-service/upload file@./path/to/file.csv
```

### Using Python Requests
```python
import requests

# Create user
response = requests.post(
    "http://localhost:8000/user-management-service/api/users",
    json={
        "username": "testuser",
        "email": "test@example.com"
    }
)
print(response.status_code)
print(response.json())

# Get user with query params
response = requests.get(
    "http://localhost:8000/user-management-service/api/users",
    params={"page": 0, "size": 10}
)
print(response.json())
```

### Load Testing with k6
```javascript
// save as load_test.js
import http from 'k6/http';
import { check } from 'k6';

export let options = {
  vus: 10,
  duration: '30s',
};

export default function() {
  // Test health endpoint
  let res = http.get('http://localhost:8000/health');
  check(res, {
    'health status is 200': (r) => r.status === 200,
  });

  // Test user service
  res = http.get('http://localhost:8000/user-management-service/api/users');
  check(res, {
    'user list status is 200': (r) => r.status === 200,
  });

  // Test contract service
  res = http.get('http://localhost:8000/contract-managment-service/v1/contracts');
  check(res, {
    'contract list status is 200': (r) => r.status === 200,
  });
}
```

Run load test:
```bash
k6 run load_test.js
```

### Postman Collection

Import this collection into Postman:

```json
{
  "info": {
    "name": "API Gateway Collection",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "item": [
    {
      "name": "Health Check",
      "request": {
        "method": "GET",
        "url": "{{gateway_url}}/health"
      }
    },
    {
      "name": "Create User",
      "request": {
        "method": "POST",
        "url": "{{gateway_url}}/user-management-service/api/users",
        "header": [
          {"key": "Content-Type", "value": "application/json"}
        ],
        "body": {
          "mode": "raw",
          "raw": "{\n  \"username\": \"testuser\",\n  \"email\": \"test@example.com\"\n}"
        }
      }
    },
    {
      "name": "Get Users",
      "request": {
        "method": "GET",
        "url": "{{gateway_url}}/user-management-service/api/users"
      }
    },
    {
      "name": "List Contracts",
      "request": {
        "method": "GET",
        "url": "{{gateway_url}}/contract-managment-service/v1/contracts"
      }
    },
    {
      "name": "List Entities",
      "request": {
        "method": "GET",
        "url": "{{gateway_url}}/entity-service/api/entities"
      }
    },
    {
      "name": "Get Timesheets",
      "request": {
        "method": "GET",
        "url": "{{gateway_url}}/timesheet-management-service/api/timesheets"
      }
    }
  ],
  "variable": [
    {
      "key": "gateway_url",
      "value": "http://localhost:8000",
      "type": "string"
    }
  ]
}
```

## Debugging

### Enable Debug Logging
```bash
LOG_LEVEL=DEBUG python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Check Correlation IDs
```bash
curl -v http://localhost:8000/user-management-service/api/users 2>&1 | grep -i correlation
```

### Monitor Request Flow
```bash
# Terminal 1 - Start gateway with debug logging
LOG_LEVEL=DEBUG python -m uvicorn app.main:app --reload

# Terminal 2 - Make request and watch logs
curl -X GET http://localhost:8000/user-management-service/api/users
```

### Test Path Rewriting
The gateway should remove service prefixes before forwarding:

```bash
# This request:
curl http://localhost:8000/user-management-service/api/users

# Should forward to:
http://localhost:8001/api/users

# Verify by checking upstream service logs
```

### Network Troubleshooting
```bash
# Check if upstream services are running
netstat -an | grep 8001
netstat -an | grep 8002
netstat -an | grep 8003
netstat -an | grep 8004

# Test direct connection to upstream service
curl http://localhost:8001/api/users
curl http://localhost:8002/v1/contracts
curl http://localhost:8003/api/entities
curl http://localhost:8004/api/timesheets
```

## Automated Testing

### Using pytest

```python
# tests/test_gateway.py
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_user_service_routing():
    response = client.get("/user-management-service/api/users")
    # Should forward request to http://localhost:8001/api/users
    assert response.status_code in [200, 503]  # 503 if service not running

def test_contract_service_routing():
    response = client.get("/contract-managment-service/v1/contracts")
    assert response.status_code in [200, 503]

def test_path_not_found():
    response = client.get("/invalid-service/endpoint")
    assert response.status_code == 404

def test_options_method():
    response = client.options("/user-management-service/api/users")
    assert response.status_code in [200, 503]
```

Run tests:
```bash
pytest tests/test_gateway.py -v
```

## Performance Testing

### Check Response Times
```bash
# Using curl with timing
curl -w "\nTime: %{time_total}s\nStatus: %{http_code}\n" \
  http://localhost:8000/user-management-service/api/users
```

### Memory Usage
```bash
# Monitor while running gateway
watch -n 1 'ps aux | grep python'
```

### Connection Pool Testing
```bash
# Concurrent requests
parallel -j 10 'curl http://localhost:8000/health' ::: $(seq 1 100)
```

## Common Issues and Solutions

### Issue: Gateway Returns 503 for Upstream Service
**Solution**: Verify upstream service is running
```bash
python -m uvicorn app.main:app --port 8001  # Example user service
```

### Issue: CORS Errors in Browser
**Solution**: Add frontend origin to CORS_ORIGINS
```env
CORS_ORIGINS=https://smmc-io-prod.timesmart.io,http://localhost:3000
```

### Issue: Request Timeout (504)
**Solution**: Increase timeout or fix slow upstream service
```env
REQUEST_TIMEOUT_SECONDS=60
```

### Issue: Path Not Found (404)
**Solution**: Verify path matches a configured route
- Check path starts with valid prefix: `/user-management-service`, `/contract-managment-service`, etc.
- Check ROUTE_PREDICATES in gateway_routes.py

### Issue: Wrong Path Forwarded
**Solution**: Check path rewriting logic
- Remove service prefix from path before forwarding
- Example: `/user-management-service/api/users` → `/api/users`

---

**Last Updated**: December 2025
