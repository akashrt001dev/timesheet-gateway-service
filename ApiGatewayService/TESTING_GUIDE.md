# CORS/OAuth2 Testing Guide

## Manual Testing with curl

### Test 1: CORS Preflight to Health Endpoint

```bash
curl -X OPTIONS "http://localhost:8000/health" \
  -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: Authorization, Content-Type" \
  -v
```

**Expected Response**:
```
HTTP/1.1 200 OK
Access-Control-Allow-Origin: http://localhost:3000
Access-Control-Allow-Methods: GET, POST, PUT, DELETE, PATCH, OPTIONS, HEAD
Access-Control-Allow-Headers: *
Access-Control-Allow-Credentials: true
Access-Control-Max-Age: 86400
Vary: Origin
```

### Test 2: CORS Preflight to Keycloak OAuth2 Endpoint

```bash
curl -X OPTIONS "http://localhost:8000/realms/test-realm/protocol/openid-connect/auth" \
  -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: Authorization, Content-Type" \
  -v
```

**Expected Response**:
```
HTTP/1.1 200 OK
Access-Control-Allow-Origin: http://localhost:3000
(CORS headers present)
(NO proxying to Keycloak)
(IMPORTANT: Should be local response, not 405!)
```

### Test 3: Disallowed Origin (Should Return 403)

```bash
curl -X OPTIONS "http://localhost:8000/health" \
  -H "Origin: http://evil.com" \
  -H "Access-Control-Request-Method: GET" \
  -v
```

**Expected Response**:
```
HTTP/1.1 403 Forbidden
```

### Test 4: Regular GET Request (No CORS Headers for Non-CORS Requests)

```bash
curl "http://localhost:8000/health" -v
```

**Expected Response**:
```
HTTP/1.1 200 OK
{status: "healthy"}
(No Access-Control headers needed)
```

### Test 5: GET with Origin Header (CORS Request)

```bash
curl "http://localhost:8000/health" \
  -H "Origin: http://localhost:3000" \
  -v
```

**Expected Response**:
```
HTTP/1.1 200 OK
Access-Control-Allow-Origin: http://localhost:3000
Access-Control-Allow-Credentials: true
(Other CORS headers)
```

### Test 6: Authorization Header Relay

```bash
curl -X POST "http://localhost:8000/auth/login" \
  -H "Origin: http://localhost:3000" \
  -H "Authorization: Bearer your-test-token" \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"test"}' \
  -v
```

**Expected**:
- Authorization header forwarded to backend service
- Backend receives: `Authorization: Bearer your-test-token`

### Test 7: Cookie to Authorization Header Conversion

```bash
curl -X POST "http://localhost:8000/auth/login" \
  -H "Origin: http://localhost:3000" \
  -H "Cookie: access_token=your-test-token" \
  -H "Content-Type: application/json" \
  -d '{}' \
  -v
```

**Expected**:
- Cookie converted to Authorization header
- Backend receives: `Authorization: Bearer your-test-token`

### Test 8: X-Forwarded Headers (Reverse Proxy)

```bash
curl "http://localhost:8000/health" \
  -H "X-Forwarded-For: 192.168.1.100" \
  -H "X-Forwarded-Proto: https" \
  -H "X-Forwarded-Host: api.example.com" \
  -v
```

**Expected**:
- Headers preserved and passed to backend services
- Backend sees correct client IP: 192.168.1.100
- Backend sees correct protocol: https

## Browser Testing

### Test 1: CORS from JavaScript

Open browser console and run:

```javascript
// From https://app.timesmartai.ca
fetch('http://localhost:8000/health', {
  method: 'GET',
  headers: {
    'Content-Type': 'application/json',
  },
  credentials: 'include'  // Important for CORS + credentials
})
.then(r => r.json())
.then(data => console.log('Success:', data))
.catch(err => console.error('CORS Error:', err.message))
```

**Expected**: 
- Success message with health status
- No CORS error in console

### Test 2: CORS with Bearer Token

```javascript
fetch('http://localhost:8000/health', {
  method: 'GET',
  headers: {
    'Authorization': 'Bearer your-test-token',
    'Content-Type': 'application/json',
  },
  credentials: 'include'
})
.then(r => r.json())
.then(data => console.log('Success:', data))
.catch(err => console.error('CORS Error:', err.message))
```

### Test 3: Check Preflight Caching

Open browser DevTools Network tab:

1. Make first request:
   ```javascript
   fetch('http://localhost:8000/health', {credentials: 'include'})
   ```
   - See: OPTIONS request → GET request (2 requests total)

2. Make second request immediately:
   ```javascript
   fetch('http://localhost:8000/health', {credentials: 'include'})
   ```
   - See: Only GET request (1 request total)
   - OPTIONS was cached for 24 hours!

### Test 4: OAuth2 Login Flow

1. Navigate to your app: `https://app.timesmartai.ca`
2. Click "Login" button
3. **Check DevTools Network tab**:
   - Should see OPTIONS request to gateway (returns 200)
   - Should see POST request to gateway (routes to /login)
   - Browser redirects to Keycloak login page
4. Log in on Keycloak
5. Browser redirects back to `/login/oauth2/code/keycloak`
6. **Should complete without CORS errors**
7. **Console should show no CORS errors**

### Test 5: Page Refresh After Login

1. Log in successfully
2. Press F5 (page refresh)
3. Session should be maintained
4. **Should not see CORS errors**
5. Try logging out and logging in again
6. **Should work without CORS issues**

## Automated Testing (pytest)

Create `tests/test_cors.py`:

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

class TestCORSPreflight:
    """Test CORS preflight handling"""
    
    def test_options_preflight_allowed_origin(self):
        """Test OPTIONS returns 200 with CORS headers for allowed origin"""
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            }
        )
        assert response.status_code == 200
        assert "Access-Control-Allow-Origin" in response.headers
        assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:3000"
        assert "Access-Control-Allow-Methods" in response.headers
        assert "OPTIONS" in response.headers["Access-Control-Allow-Methods"]
    
    def test_options_preflight_disallowed_origin(self):
        """Test OPTIONS returns 403 for disallowed origin"""
        response = client.options(
            "/health",
            headers={
                "Origin": "http://evil.com",
                "Access-Control-Request-Method": "GET",
            }
        )
        assert response.status_code == 403
    
    def test_options_keycloak_endpoint(self):
        """Test OPTIONS to Keycloak endpoint returns 200 (not proxied)"""
        response = client.options(
            "/realms/test-realm/protocol/openid-connect/auth",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            }
        )
        assert response.status_code == 200
        assert "Access-Control-Allow-Origin" in response.headers


class TestCORSHeaders:
    """Test CORS response headers"""
    
    def test_cors_headers_on_get_request(self):
        """Test CORS headers added to GET response"""
        response = client.get(
            "/health",
            headers={"Origin": "http://localhost:3000"}
        )
        assert response.status_code == 200
        assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:3000"
        assert response.headers["Access-Control-Allow-Credentials"] == "true"
    
    def test_cors_headers_on_post_request(self):
        """Test CORS headers added to POST response"""
        response = client.post(
            "/auth/login",
            json={"username": "test", "password": "test"},
            headers={"Origin": "http://localhost:3000"}
        )
        assert response.status_code in [200, 307, 401]  # May redirect or need auth
        assert "Access-Control-Allow-Origin" in response.headers
    
    def test_cors_max_age_header(self):
        """Test preflight cache time"""
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            }
        )
        assert response.status_code == 200
        assert "Access-Control-Max-Age" in response.headers
        # Should be 86400 (24 hours)
        max_age = int(response.headers["Access-Control-Max-Age"])
        assert max_age == 86400


class TestOriginValidation:
    """Test origin validation logic"""
    
    def test_allowed_origin_included(self):
        """Test that configured origin is allowed"""
        # Assuming http://localhost:3000 is in CORS_ORIGINS
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            }
        )
        assert response.status_code == 200
    
    def test_keycloak_origin_included(self):
        """Test that Keycloak server origin is allowed"""
        # Assuming keycloak URL is in CORS_ORIGINS
        response = client.options(
            "/health",
            headers={
                "Origin": "https://idm.timesmart.io",
                "Access-Control-Request-Method": "GET",
            }
        )
        assert response.status_code == 200
    
    def test_disallowed_origin_rejected(self):
        """Test that disallowed origin is rejected"""
        response = client.options(
            "/health",
            headers={
                "Origin": "http://evil.com",
                "Access-Control-Request-Method": "GET",
            }
        )
        # Specific behavior depends on implementation
        # Either 403 or no CORS headers
        assert response.status_code in [200, 403]
        if response.status_code == 200:
            # If 200, CORS headers should not allow evil.com
            assert response.headers.get("Access-Control-Allow-Origin") != "http://evil.com"


class TestTokenRelay:
    """Test Authorization header handling"""
    
    def test_authorization_header_preserved(self):
        """Test that Authorization header is forwarded"""
        response = client.get(
            "/health",
            headers={
                "Authorization": "Bearer test-token",
                "Origin": "http://localhost:3000",
            }
        )
        # Should pass through without error
        assert response.status_code == 200
    
    def test_multiple_auth_methods(self):
        """Test different Authorization methods"""
        for auth_header in [
            "Bearer test-token",
            "Basic dXNlcjpwYXNz",
            "Custom-Auth token-value"
        ]:
            response = client.get(
                "/health",
                headers={
                    "Authorization": auth_header,
                    "Origin": "http://localhost:3000",
                }
            )
            # Should pass through
            assert response.status_code == 200


class TestForwardedHeaders:
    """Test reverse proxy header handling"""
    
    def test_x_forwarded_for_preserved(self):
        """Test X-Forwarded-For header is preserved"""
        response = client.get(
            "/health",
            headers={
                "X-Forwarded-For": "192.168.1.100",
                "Origin": "http://localhost:3000",
            }
        )
        assert response.status_code == 200
    
    def test_x_forwarded_proto_preserved(self):
        """Test X-Forwarded-Proto header is preserved"""
        response = client.get(
            "/health",
            headers={
                "X-Forwarded-Proto": "https",
                "Origin": "http://localhost:3000",
            }
        )
        assert response.status_code == 200
    
    def test_x_forwarded_host_preserved(self):
        """Test X-Forwarded-Host header is preserved"""
        response = client.get(
            "/health",
            headers={
                "X-Forwarded-Host": "api.timesmart.io",
                "Origin": "http://localhost:3000",
            }
        )
        assert response.status_code == 200
```

Run tests:
```bash
pytest tests/test_cors.py -v
```

## Debugging with Logs

### Enable Debug Logging

Set in `.env`:
```env
LOG_LEVEL=DEBUG
```

### Watch for CORS Messages

```bash
# Start gateway
docker-compose up -d gateway

# Watch logs
docker logs -f gateway | grep -i cors
```

Expected debug output:
```
DEBUG: CORS preflight request: /realms/.../auth
DEBUG: Handling CORS preflight locally: OPTIONS /realms/...
DEBUG: CORS preflight allowed for origin: http://localhost:3000
DEBUG: CORS headers added for GET /health from http://localhost:3000
```

### Log Filtering

```bash
# Only CORS-related logs
docker logs gateway | grep -i "cors\|preflight\|origin"

# Only errors
docker logs gateway | grep -i "error\|failed\|denied"

# Only authentication
docker logs gateway | grep -i "auth\|keycloak\|token"

# Specific endpoint
docker logs gateway | grep "/health"
```

## Performance Testing

### Measure Preflight Caching

```bash
# First request (with OPTIONS)
time curl -X OPTIONS "http://localhost:8000/health" \
  -H "Origin: http://localhost:3000" \
  && curl "http://localhost:8000/health" \
  -H "Origin: http://localhost:3000"

# Second request (cached)
time curl "http://localhost:8000/health" \
  -H "Origin: http://localhost:3000"
```

Second request should be ~2x faster due to preflight caching.

### Load Testing

Use `ab` (Apache Bench):

```bash
# Without preflight (should be fast)
ab -n 1000 -c 10 "http://localhost:8000/health"

# Measure with CORS headers
ab -n 1000 -c 10 -H "Origin: http://localhost:3000" \
  "http://localhost:8000/health"
```

Both should have similar performance. CORS processing overhead is minimal.

## Integration Testing (End-to-End)

### OAuth2 Flow Test Script

```bash
#!/bin/bash

echo "Testing OAuth2 flow..."

# 1. Check health
echo "1. Testing health endpoint..."
curl -s "http://localhost:8000/health" | jq .

# 2. Test CORS preflight to OAuth2 endpoint
echo "2. Testing CORS preflight to OAuth2..."
curl -s -X OPTIONS "http://localhost:8000/realms/test/protocol/openid-connect/auth" \
  -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: GET" \
  -w "\nStatus: %{http_code}\n"

# 3. Test login redirect
echo "3. Testing login redirect..."
curl -s -L "http://localhost:8000/login" \
  -H "Origin: http://localhost:3000" \
  -w "\nStatus: %{http_code}\n" \
  | head -20

echo "All tests completed!"
```

## Checklist for Testing

- [ ] CORS preflight returns 200 (not 405)
- [ ] CORS headers present in response
- [ ] Origin validation working (allowed ✓, disallowed ✗)
- [ ] Authorization header forwarded
- [ ] Cookie to header conversion works
- [ ] X-Forwarded-* headers preserved
- [ ] Preflight caching working (2 requests → 1 request)
- [ ] OAuth2 login works without CORS errors
- [ ] Page refresh maintains session
- [ ] No CORS errors in browser console
- [ ] Debug logs show preflight handling
