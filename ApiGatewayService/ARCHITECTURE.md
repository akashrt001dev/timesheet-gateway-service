# API Gateway Architecture & Design

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           INCOMING REQUESTS                             │
│                        (All HTTP Methods)                               │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                    ┌────────────────▼────────────────┐
                    │   FastAPI Gateway (Port 8000)   │
                    │                                 │
                    │  1. Health Check Endpoint       │
                    │  2. Universal Route Handler     │
                    │  3. Exception Handlers          │
                    └────────────────┬────────────────┘
                                     │
         ┌───────────────────────────┼───────────────────────────┐
         │        MIDDLEWARE STACK   │                           │
         │                           │                           │
         │  ┌──────────────────────┐│                           │
         │  │ CORS Middleware      ││ Origin validation        │
         │  └──────────────────────┘│                           │
         │  ┌──────────────────────┐│                           │
         │  │ Header Removal       ││ Security filtering       │
         │  └──────────────────────┘│                           │
         │  ┌──────────────────────┐│                           │
         │  │ Request Logging      ││ Audit trail             │
         │  └──────────────────────┘│                           │
         │  ┌──────────────────────┐│                           │
         │  │ Correlation ID       ││ Request tracing         │
         │  └──────────────────────┘│                           │
         │  ┌──────────────────────┐│                           │
         │  │ Authentication       ││ JWT validation          │
         │  └──────────────────────┘│                           │
         │                           │                           │
         └───────────────────────────┼───────────────────────────┘
                                     │
                    ┌────────────────▼────────────────┐
                    │   ROUTE DETERMINATION           │
                    │                                 │
                    │  determine_target_service()    │
                    │  - Match path prefix            │
                    │  - Return service URL           │
                    └────────────────┬────────────────┘
                                     │
        ┌────────────────┬───────────┼────────────┬──────────────┐
        │                │           │            │              │
        ▼                ▼           ▼            ▼              ▼
    ┌────────┐    ┌─────────┐ ┌──────────┐ ┌─────────────┐ ┌──────────┐
    │Frontend │   │ User    │ │Contract  │ │Entity       │ │Timesheet │
    │(Ext)   │   │Service  │ │Service   │ │Service      │ │Service   │
    │        │   │(8001)   │ │(8002)    │ │(8003)       │ │(8004)    │
    │HTTPS   │   │HTTP     │ │HTTP      │ │HTTP         │ │HTTP      │
    └────────┘   └─────────┘ └──────────┘ └─────────────┘ └──────────┘
```

## Request Processing Flow

```
1. INCOMING REQUEST
   ├─ Method: GET/POST/PUT/PATCH/DELETE/OPTIONS/HEAD
   ├─ Path: /service-prefix/resource/id?params
   └─ Headers: Authorization, Content-Type, etc.
        │
        ▼
2. MIDDLEWARE CHAIN
   ├─ CORS: Validate origin
   ├─ Header Removal: Strip sensitive headers
   ├─ Request Logging: Log incoming request
   ├─ Correlation ID: Add X-Correlation-ID
   └─ Authentication: Validate JWT
        │
        ▼
3. GATEWAY ROUTE HANDLER
   ├─ Extract path from request
   └─ Call gateway_route()
        │
        ▼
4. SERVICE ROUTING
   ├─ Call determine_target_service(path)
   ├─ Match path prefix against ROUTE_PREDICATES
   ├─ Return (service_id, service_url)
   └─ Raise 404 if no match
        │
        ▼
5. PATH REWRITING
   ├─ Call rewrite_path_for_upstream(path, service_id)
   ├─ Remove service prefix from path
   ├─ Normalize path
   └─ Return rewritten path
        │
        ▼
6. PROXY REQUEST (Core Function)
   ├─ Build target URL: service_url + rewritten_path
   ├─ Prepare headers: Filter hop-by-hop headers
   ├─ Read body: For POST/PUT/PATCH
   ├─ Create httpx AsyncClient
   ├─ Forward request to upstream service
   ├─ Handle redirects (follow_redirects=True)
   ├─ Catch exceptions:
   │  ├─ TimeoutException → 504
   │  ├─ ConnectError → 503
   │  └─ Generic Exception → 502
   └─ Return (status_code, headers, body)
        │
        ▼
7. RESPONSE HANDLING
   ├─ Extract status code from response
   ├─ Filter response headers (remove hop-by-hop)
   ├─ Read response body
   ├─ Create StreamingResponse
   └─ Return to client
        │
        ▼
8. RESPONSE TO CLIENT
   ├─ Status Code: From upstream service
   ├─ Headers: Forwarded from upstream
   ├─ Body: Streamed content
   └─ Content-Type: Preserved
```

## Route Matching Algorithm

```
Input: Request path (e.g., "/user-management-service/api/users")

Algorithm:
  1. Sort ROUTE_PREDICATES by prefix length (descending)
  2. For each prefix in sorted order:
     - If path starts with prefix:
       - Get service_id from ROUTE_PREDICATES[prefix]
       - Get service_url from UPSTREAM_SERVICES[service_id]
       - If service_url found:
         - MATCH FOUND → Return (service_id, service_url)
  3. If no match found:
     - Return ("frontend", FRONTEND_URL)

Example:
  path = "/user-management-service/api/users"
  
  Sorted prefixes: ["/user-management-service", "/auth", "/user", "/roles"]
  
  Check "/user-management-service"?
    ✓ YES - "/user-management-service/api/users" starts with it
    → service_id = "user-management-service"
    → service_url = "http://localhost:8001"
    ✓ MATCH → Return ("user-management-service", "http://localhost:8001")
```

## Path Rewriting Logic

```
Input: path = "/contract-managment-service/v1/contracts"
       service_id = "contract-managment-service"

Algorithm:
  1. Find all ROUTE_PREDICATES entries where value == service_id
  2. Sort by prefix length (descending)
  3. For each prefix:
     - If path starts with prefix:
       - Remove prefix from path
       - Ensure path starts with /
       - RETURN rewritten path

Example 1:
  Input: path = "/contract-managment-service/v1/contracts"
         service_id = "contract-managment-service"
  
  Predicates for service:
    - "/contract-managment-service"
    - "/contract-management-service"
    - "/contracts"
  
  Sorted: ["/contract-managment-service", "/contract-management-service", "/contracts"]
  
  Check "/contract-managment-service"?
    ✓ YES - path starts with it
    Remove prefix: "v1/contracts" (add /)
    → "/v1/contracts"

Example 2:
  Input: path = "/auth/login"
         service_id = "user-management-service"
  
  Predicates for service:
    - "/user-management-service"
    - "/auth"
    - "/user"
    - "/roles"
  
  Sorted: ["/user-management-service", "/auth", "/user", "/roles"]
  
  Check "/user-management-service"? NO
  Check "/auth"? ✓ YES
  Remove prefix: "login" (add /)
  → "/login"
```

## Proxy Request Helper Function

```python
async def proxy_request(
    request: Request,
    upstream_url: str,
    upstream_path: str,
    timeout: float = HTTPX_TIMEOUT
) -> Tuple[int, Dict[str, str], bytes]:
    """
    Core reverse proxy implementation
    
    Inputs:
      - request: FastAPI Request object
      - upstream_url: Base URL (http://localhost:8001)
      - upstream_path: Path (/api/users)
      - timeout: Request timeout (30 seconds)
    
    Process:
      1. Build target URL:
         - Combine upstream_url + upstream_path
         - Append query parameters if present
         Example: http://localhost:8001/api/users?page=0&size=10
      
      2. Prepare headers:
         - Iterate through request.headers
         - Skip hop-by-hop headers (Connection, Transfer-Encoding, etc.)
         - Keep: Authorization, Content-Type, Accept, etc.
         - Add: X-Correlation-ID (from middleware)
      
      3. Read request body:
         - For POST, PUT, PATCH: await request.body()
         - For GET, DELETE, OPTIONS, HEAD: empty body
      
      4. Create HTTP client:
         - httpx.AsyncClient with connection pooling
         - Configured timeouts
         - Follow redirects enabled
      
      5. Forward request:
         - HTTP method: request.method.upper()
         - URL: target_url
         - Headers: prepared headers
         - Content: request body (if present)
      
      6. Handle response:
         - Extract status code
         - Filter response headers
         - Read response content
      
      7. Error handling:
         - httpx.TimeoutException → HTTPException 504
         - httpx.ConnectError → HTTPException 503
         - Generic Exception → HTTPException 502
    
    Outputs:
      - Tuple: (status_code: int, headers: Dict, body: bytes)
    
    Returns:
      Example: (200, {"content-type": "application/json"}, b'{"data": [...]}')
    """
```

## Data Flow Diagram - Complete Request

```
CLIENT REQUEST
│
├─ Method: POST
├─ URL: http://localhost:8000/contract-managment-service/v1/contracts
├─ Headers: {
│    "Authorization": "Bearer token...",
│    "Content-Type": "application/json"
│  }
└─ Body: {"name": "Contract A", "type": "SERVICE"}
     │
     ▼
┌─────────────────────────────────────────┐
│ MIDDLEWARE PROCESSING                    │
│                                          │
│ ┌─ CORS Check                           │
│ ├─ Add X-Correlation-ID                 │
│ ├─ Log request                          │
│ ├─ JWT validation                       │
│ └─ Add to scope: {                      │
│     "correlation_id": "uuid-xxx",       │
│     "user": {...}                       │
│   }                                      │
└────────────────────────┬──────────────────┘
                         │
                         ▼
              ┌──────────────────────────┐
              │ gateway_route()          │
              │                          │
              │ path = "/contract-...   │
              │    /v1/contracts"       │
              └────────────┬─────────────┘
                           │
                           ▼
         ┌─────────────────────────────────────┐
         │ determine_target_service()          │
         │                                     │
         │ Match: /contract-managment-service │
         │ → ("contract-managment-service",   │
         │    "http://localhost:8002")        │
         └────────────────┬────────────────────┘
                          │
                          ▼
         ┌─────────────────────────────────────┐
         │ rewrite_path_for_upstream()         │
         │                                     │
         │ Input: "/contract-managment-...    │
         │        /v1/contracts"              │
         │                                     │
         │ Remove: "/contract-managment-...   │
         │ Output: "/v1/contracts"            │
         └────────────────┬────────────────────┘
                          │
                          ▼
         ┌─────────────────────────────────────┐
         │ proxy_request()                     │
         │                                     │
         │ Target URL: http://localhost:8002/ │
         │            v1/contracts            │
         │                                     │
         │ Forward headers (skip hop-by-hop)  │
         │ Forward body: JSON payload          │
         │                                     │
         │ Create: httpx.AsyncClient          │
         │ Request: POST http://...           │
         └────────────────┬────────────────────┘
                          │
                          ▼
                ┌──────────────────────────┐
                │ UPSTREAM SERVICE         │
                │ (Contract Service)       │
                │                          │
                │ Receive POST request     │
                │ Process request          │
                │ Return response:         │
                │ - Status: 201 Created    │
                │ - Body: {id: 123, ...}  │
                │ - Headers: {...}        │
                └────────────────┬─────────┘
                                 │
                                 ▼
         ┌─────────────────────────────────────┐
         │ Response Processing                 │
         │                                     │
         │ Extract:                            │
         │ - status_code: 201                  │
         │ - headers: (filter hop-by-hop)      │
         │ - body: response content            │
         │                                     │
         │ Return: (201, {...headers...},      │
         │         b'{...body...}')            │
         └────────────────┬────────────────────┘
                          │
                          ▼
         ┌─────────────────────────────────────┐
         │ StreamingResponse                   │
         │                                     │
         │ status_code: 201                    │
         │ headers: from upstream              │
         │ content: response body (streamed)   │
         └────────────────┬────────────────────┘
                          │
                          ▼
CLIENT RESPONSE
│
├─ Status: 201 Created
├─ Headers: from contract service
└─ Body: {"id": 123, "name": "Contract A", ...}
```

## Static Files Handling

```
REQUEST PATH → STATIC FILE CHECK → ROUTING DECISION

/styles.css
    │
    ├─ is_static_file("/styles.css")
    ├─ Check: .css in STATIC_EXTENSIONS
    ├─ Result: TRUE → is a static file
    │
    ├─ Path doesn't match service prefix
    ├─ Route to: Frontend (FRONTEND_URL)
    └─ Proxy to: https://smmc-io-prod.timesmart.io/styles.css

/user-management-service/api/users
    │
    ├─ is_static_file("/user-management-service/api/users")
    ├─ No static extension
    ├─ Result: FALSE → not a static file
    │
    ├─ Path matches service prefix
    ├─ Route to: User Service
    └─ Proxy to: http://localhost:8001/api/users
```

## Error Handling Flow

```
EXCEPTION HANDLING

1. HTTPException
   └─ Caught by @app.exception_handler(HTTPException)
      │
      ├─ Log error with correlation_id
      ├─ Return JSONResponse with:
      │  ├─ status_code
      │  ├─ detail message
      │  └─ correlation_id
      └─ Response sent to client

2. Connection Errors (httpx.ConnectError)
   └─ In proxy_request()
      │
      ├─ Log: "Connection error to {upstream_url}"
      ├─ Raise HTTPException(status_code=503)
      └─ Description: "Service unavailable"

3. Timeout Errors (httpx.TimeoutException)
   └─ In proxy_request()
      │
      ├─ Log: "Timeout proxying to {upstream_url}"
      ├─ Raise HTTPException(status_code=504)
      └─ Description: "Gateway timeout"

4. Unknown Errors (Exception)
   └─ In proxy_request()
      │
      ├─ Log: Full exception traceback
      ├─ Raise HTTPException(status_code=502)
      └─ Description: "Bad gateway"

5. Unhandled Exceptions
   └─ Caught by @app.exception_handler(Exception)
      │
      ├─ Log exception with traceback
      ├─ Return JSONResponse with:
      │  ├─ status_code: 500
      │  ├─ detail: "Internal server error"
      │  └─ correlation_id
      └─ Response sent to client
```

## Scalability Considerations

```
HORIZONTAL SCALING

Gateway Instance 1 ┐
Gateway Instance 2 ├─ Load Balancer (nginx, AWS ELB)
Gateway Instance 3 ┘          │
                              │
                    ┌─────────┴─────────┐
                    │                   │
                    ▼                   ▼
            User Service            Contract Service
            (Multiple Replicas)     (Multiple Replicas)
            
Each Gateway Instance:
  - Stateless (no local state)
  - Connection pooling (httpx.AsyncClient)
  - Configurable timeouts
  - Async request handling
  
Benefits:
  ✓ Request load distribution
  ✓ High availability
  ✓ Zero-downtime deployments
  ✓ Auto-scaling capability
```

## Security Architecture

```
┌────────────────────────────────────────────────────┐
│ INCOMING REQUEST                                    │
└─────────────────────┬──────────────────────────────┘
                      │
        ┌─────────────▼─────────────┐
        │ CORS MIDDLEWARE           │
        │ Validate Origin           │
        │ Check allowed methods     │
        └─────────────┬─────────────┘
                      │
        ┌─────────────▼─────────────┐
        │ HEADER REMOVAL            │
        │ Strip sensitive headers   │
        │ - Cookies (optional)      │
        │ - Internal headers        │
        └─────────────┬─────────────┘
                      │
        ┌─────────────▼─────────────┐
        │ AUTHENTICATION            │
        │ JWT Validation            │
        │ Extract user claims       │
        └─────────────┬─────────────┘
                      │
        ┌─────────────▼─────────────┐
        │ CORRELATION ID            │
        │ Add X-Correlation-ID      │
        │ For request tracing       │
        └─────────────┬─────────────┘
                      │
        ┌─────────────▼─────────────┐
        │ SERVICE ROUTING           │
        │ Path-based routing        │
        │ Service validation        │
        └─────────────┬─────────────┘
                      │
        ┌─────────────▼─────────────┐
        │ PROXY FORWARDING          │
        │ Forward to upstream       │
        │ TLS/SSL if needed         │
        └─────────────┬─────────────┘
                      │
        ┌─────────────▼─────────────┐
        │ RESPONSE FILTERING        │
        │ Remove hop-by-hop headers │
        │ Check content type        │
        └─────────────┬─────────────┘
                      │
┌─────────────────────▼──────────────────────────────┐
│ RESPONSE TO CLIENT                                  │
└────────────────────────────────────────────────────┘
```

---

**Architecture Version**: 1.0.0  
**Last Updated**: December 2025  
**Status**: Production Ready
