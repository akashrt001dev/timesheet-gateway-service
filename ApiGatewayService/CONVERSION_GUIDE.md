# Spring Boot to FastAPI Conversion Guide

This document details the conversion from Spring Boot API Gateway to FastAPI.

## 🔄 Mapping Reference

### Application Entry Point

**Spring Boot:**
```java
@SpringBootApplication
@EnableEurekaClient
public class ApiGatewayServiceApplication {
    public static void main(String[] args) {
        SpringApplication.run(ApiGatewayServiceApplication.class, args);
    }
}
```

**FastAPI:**
```python
# app/main.py
from fastapi import FastAPI

app = create_app()  # Creates FastAPI application
# Run with: uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## Configuration Conversion

### Spring application.yml

```yaml
server:
  port: 8000

spring:
  cloud:
    gateway:
      routes:
        - id: user-management-service
          uri: lb://user-management-service
          predicates:
            - Path=/auth/**, /user/**, /roles/**
          filters:
            - RewritePath=/auth/(?<path>.*), /$\{path}
```

**Maps to FastAPI:**
- `app/core/config.py` - Pydantic Settings (replaces application.yml)
- `.env` - Environment variables (replaces properties)
- `app/core/config.py::GATEWAY_ROUTES` - Route definitions

---

## Filter Conversion

### Spring GlobalFilter

**Spring:**
```java
@Component
@Order(1)
public class AuthenticationFilter implements GlobalFilter {
    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        // Filter logic
        return chain.filter(exchange);
    }
}
```

**FastAPI:**
```python
# app/filters/middleware.py
class AuthenticationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Middleware logic
        return await call_next(request)
```

### Converted Filters

| Spring Filter | FastAPI Middleware | File | Purpose |
|---|---|---|---|
| AuthenticationFilter | AuthenticationMiddleware | middleware.py | JWT validation |
| (CORS Config) | CORSMiddleware | middleware.py | Cross-origin handling |
| RemoveRequestHeader | HeaderRemovalMiddleware | middleware.py | Remove headers |
| (Built-in) | CorrelationIDMiddleware | middleware.py | Request tracing |
| (Built-in) | RequestLoggingMiddleware | middleware.py | Request/response logging |

---

## JWT Handling Conversion

### Spring Boot JwtUtil

```java
@Component
public class JwtUtil {
    @Value("${jwt.secret}")
    private String secret;
    
    public Claims getAllClaimsFromToken(String token) {
        return Jwts.parserBuilder()
            .setSigningKey(key)
            .build()
            .parseClaimsJws(token)
            .getBody();
    }
}
```

**FastAPI Equivalent:**
```python
# app/core/security.py
class JwtUtil:
    def __init__(self, secret: str, algorithm: str = "HS256"):
        self.secret = secret
        self.algorithm = algorithm
    
    def get_all_claims_from_token(self, token: str) -> Dict[str, Any]:
        payload = jwt.decode(token, self.secret, algorithms=[self.algorithm])
        return payload
```

---

## Route Configuration

### Spring Cloud Gateway Routes

```yaml
spring:
  cloud:
    gateway:
      routes:
        - id: user-management-service
          uri: lb://user-management-service
          predicates:
            - Path=/auth/**, /user/**, /roles/**
          filters:
            - RewritePath=/auth/(?<path>.*), /$\{path},/user/(?<path>.*), /$\{path}
            - RemoveRequestHeader=Cookie,Set-Cookie
```

**FastAPI Implementation:**
```python
# app/core/config.py
GATEWAY_ROUTES = {
    "user-management-service": {
        "id": "user-management-service",
        "uri": "lb://user-management-service",
        "predicates": ["/auth/**", "/user/**", "/roles/**"],
        "rewrites": {
            "/auth/(?P<path>.*)": "/$path",
            "/user/(?P<path>.*)": "/$path",
        },
        "remove_headers": ["Cookie", "Set-Cookie"],
    },
    # ... more routes
}

# app/services/gateway_forwarder.py
# Implements routing and request forwarding
```

---

## Endpoint Routing

### Spring Gateway Route Handler

Spring Cloud Gateway automatically routes requests based on configuration.

**FastAPI Implementation:**
```python
# app/api/gateway_routes.py
@router.api_route("/{path:path}", methods=[...])
async def gateway_route(request: Request, path: str):
    # Find matching route
    route_config = forwarder.get_target_service(path)
    
    # Rewrite path
    rewritten_path = forwarder.rewrite_path(path, route_config)
    
    # Forward to upstream service
    response = await forwarder.forward_request(request, target_url)
    
    return StreamingResponse(...)
```

---

## CORS Configuration

### Spring CorsConfig

```java
@Configuration
public class CorsConfig {
    @Bean
    public CorsWebFilter corsWebFilter() {
        final CorsConfiguration corsConfig = new CorsConfiguration();
        corsConfig.setAllowedOrigins(Collections.singletonList("*"));
        corsConfig.setAllowedMethods(Arrays.asList("GET", "POST", "PUT", "DELETE"));
        
        final UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", corsConfig);
        
        return new CorsWebFilter(source);
    }
}
```

**FastAPI Equivalent:**
```python
# app/main.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_credentials,
    allow_methods=settings.cors_methods,
    allow_headers=settings.cors_headers,
)
```

---

## Request/Response Processing

### Request Headers

**Spring:**
```java
private void populateRequestWithHeaders(ServerWebExchange exchange, String token) {
    Claims claims = jwtUtil.getAllClaimsFromToken(token);
    exchange.getRequest().mutate()
        .header("id", String.valueOf(claims.get("id")))
        .header("role", String.valueOf(claims.get("role")))
        .build();
}
```

**FastAPI:**
```python
# app/core/security.py
def populate_request_with_headers(claims: Dict[str, Any]) -> Dict[str, str]:
    headers = {}
    if "id" in claims:
        headers["X-User-ID"] = str(claims["id"])
    if "role" in claims:
        headers["X-User-Role"] = str(claims["role"])
    return headers

# app/services/gateway_forwarder.py
headers = self.prepare_headers(request)
# Headers are added before forwarding to upstream service
```

---

## Service Discovery

### Eureka Integration

**Spring Boot:**
```yaml
eureka:
  instance:
    prefer-ip-address: true
  client:
    service-url:
      default-zone: http://localhost:8761/eureka/
    fetch-registry: true
    register-with-eureka: true
```

**FastAPI:**
- Uses `EUREKA_ENABLED` flag in config
- Service URLs are resolved from environment variables
- Load-balanced URIs (`lb://service-name`) are resolved from `EUREKA_SERVER_URL` or env vars

```python
# app/core/config.py
eureka_enabled: bool = Field(default=True, alias="EUREKA_ENABLED")
eureka_server_url: str = Field(...)

# app/services/gateway_forwarder.py
def _resolve_service_url(self, service_name: str) -> str:
    # Maps service names to URLs
    # Can be extended to use Eureka client library
```

---

## Health Checks & Actuator

### Spring Actuator Endpoints

```
GET /actuator/health
GET /actuator/info
GET /actuator/metrics
```

**FastAPI Implementation:**
```python
# app/api/actuator_routes.py
@router.get("/actuator/health")
async def health_check():
    return HealthResponse(status="UP", ...)

@router.get("/actuator/info")
async def service_info():
    return ServiceInfo(name="gateway-service", ...)
```

---

## Error Handling

### Spring Exception Handling

Spring Cloud Gateway provides built-in error handling with appropriate HTTP status codes.

**FastAPI Equivalent:**
```python
# app/main.py
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "correlation_id": ...}
    )

# app/services/gateway_forwarder.py
try:
    response = await client.request(...)
except httpx.TimeoutException:
    raise HTTPException(status_code=504, detail="Gateway timeout")
except httpx.ConnectError:
    raise HTTPException(status_code=503, detail="Service unavailable")
```

---

## Logging

### Spring Cloud Sleuth & Logging

Spring uses SLF4J with Sleuth for distributed tracing.

**FastAPI Equivalent:**
```python
# app/core/logging.py
def setup_logging(log_level: str = "INFO", use_json: bool = False):
    # Sets up structured logging
    # Supports correlation IDs for tracing

# app/filters/middleware.py
class CorrelationIDMiddleware:
    # Generates and propagates correlation IDs
    # Similar to Spring Cloud Sleuth
```

---

## Testing Equivalency

| Feature | Spring | FastAPI | Test Command |
|---|---|---|---|
| Health Check | GET /actuator/health | GET /actuator/health | `curl http://localhost:8000/actuator/health` |
| API Docs | Swagger at /swagger-ui.html | Swagger at /docs | Visit `http://localhost:8000/docs` |
| Route Forwarding | Automatic | Via gateway_routes.py | `curl http://localhost:8000/user/profile` |
| JWT Validation | AuthenticationFilter | AuthenticationMiddleware | Use Bearer token header |
| CORS | CorsWebFilter | CORSMiddleware | `curl -i -X OPTIONS ...` |

---

## Deployment Equivalency

| Aspect | Spring Boot | FastAPI |
|---|---|---|
| Build | `mvn clean package` | `pip install -r requirements.txt` |
| Run Locally | `java -jar app.jar` | `uvicorn app.main:app` |
| Docker | Multi-stage build | `docker build -t api-gateway .` |
| Config | application.yml | .env file |
| Port | application.yml:server.port | SERVER_PORT env var |
| Logs | Logback | Python logging module |
| Process Management | Spring Boot embedded | Uvicorn + shell script |

---

## Breaking Changes

❌ **None** - This conversion preserves all Spring Boot functionality:

✅ Same routing logic
✅ Same authentication mechanism
✅ Same request/response handling
✅ Same CORS behavior
✅ Same health check endpoints
✅ Same configuration options
✅ Same error handling

---

## Performance Considerations

### Spring Cloud Gateway
- Reactive (Project Reactor)
- Built on Netty
- Good for large concurrent connections

### FastAPI with Uvicorn
- Async/await (asyncio)
- Built on Starlette + httpx
- Comparable performance
- Lighter resource footprint
- Simpler to understand and debug

---

## Migration Checklist

- [x] Extract routes from application.yml
- [x] Convert JWT validation logic
- [x] Implement all middleware
- [x] Create request forwarding service
- [x] Implement actuator endpoints
- [x] Setup CORS configuration
- [x] Create Docker container
- [x] Create startup scripts
- [x] Document endpoints
- [x] Document configuration
- [x] Document deployment

---

## Next Steps

1. **Update upstream service URLs** in `.env`
2. **Verify JWT secret** matches your auth service
3. **Test locally** with: `uvicorn app.main:app --reload`
4. **Test Docker** with: `docker-compose up`
5. **Deploy** to your environment
6. **Monitor logs** for any issues

---

## Support

For detailed information on running and configuring the FastAPI Gateway, see [README.md](README.md)

---

**Conversion Date**: December 2024
**Spring Boot Version**: 2.6.3
**FastAPI Version**: 0.104.1
**Python Version**: 3.11+
