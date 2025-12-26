# FastAPI Gateway Service

> A high-performance API Gateway built with FastAPI - Converted from Spring Cloud Gateway

## 📋 Overview

This is a complete Python/FastAPI conversion of the Spring Boot API Gateway service. It provides:

- **API Gateway** - Routes requests to appropriate microservices
- **JWT Authentication** - Validates tokens and extracts user claims
- **CORS Handling** - Configurable cross-origin resource sharing
- **Request/Response Logging** - Structured logging with correlation IDs
- **Service Discovery** - Eureka integration support (optional)
- **Health Checks** - Actuator endpoints for monitoring
- **Docker Support** - Production-ready Docker containerization

## 🛠️ Technology Stack

- **Python** 3.11+
- **FastAPI** - Modern web framework
- **Uvicorn** - ASGI server
- **httpx** - Async HTTP client for forwarding requests
- **Pydantic v2** - Data validation
- **PyJWT** - JWT token handling
- **Docker** - Containerization

## 📁 Project Structure

```
ApiGatewayService/
├── app/
│   ├── __init__.py
│   ├── main.py                      # FastAPI application entry point
│   ├── api/
│   │   ├── __init__.py
│   │   ├── gateway_routes.py        # Universal gateway route handler
│   │   └── actuator_routes.py       # Health check and monitoring endpoints
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                # Configuration (Pydantic Settings)
│   │   ├── security.py              # JWT validation and security
│   │   └── logging.py               # Structured logging configuration
│   ├── services/
│   │   ├── __init__.py
│   │   └── gateway_forwarder.py     # Request forwarding logic
│   ├── filters/
│   │   ├── __init__.py
│   │   └── middleware.py            # All middleware (auth, logging, CORS, etc.)
│   └── utils/
│       └── __init__.py
├── startup.sh                        # Linux/macOS startup script
├── startup.bat                       # Windows startup script
├── .env                              # Environment variables
├── .env.example                      # Example environment variables
├── requirements.txt                  # Python dependencies
├── Dockerfile                        # Docker image definition
├── .dockerignore                     # Files to exclude from Docker image
├── docker-compose.yml               # Docker Compose for full stack
└── README.md                         # This file
```

## 🚀 Quick Start

### Local Development

#### 1. Prerequisites

- Python 3.11 or higher
- pip (Python package manager)
- Virtual environment support

#### 2. Setup

```bash
# Clone the repository
cd ApiGatewayService

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment variables
cp .env.example .env
# Edit .env with your configuration
```

#### 3. Configure Services

Edit `.env` file with your upstream service URLs:

```env
USER_SERVICE_URL=http://localhost:8001
CONTRACT_SERVICE_URL=http://localhost:8002
ENTITY_SERVICE_URL=http://localhost:8003
TIMESHEET_SERVICE_URL=http://localhost:8004
```

#### 4. Run the Gateway

```bash
# Using Uvicorn directly
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Or using the startup script (Linux/macOS)
chmod +x scripts/start_gateway.sh
./scripts/start_gateway.sh start

# Or on Windows
scripts\start_gateway.bat start
```

#### 5. Verify It's Running

```bash
# Check health
curl http://localhost:8000/actuator/health

# Check service info
curl http://localhost:8000/actuator/info

# Access API documentation
# Swagger UI: http://localhost:8000/docs
# ReDoc: http://localhost:8000/redoc
```

## 🐳 Docker Deployment

### Option 1: Docker Compose (Full Stack with Eureka)

```bash
# Build and run with Docker Compose
docker-compose up -d

# Check logs
docker-compose logs -f api-gateway

# Stop services
docker-compose down
```

### Option 2: Docker Build Only

```bash
# Build Docker image
docker build -t api-gateway-service:1.0 .

# Run container
docker run -d \
  --name api-gateway \
  -p 8000:8000 \
  --env-file .env \
  api-gateway-service:1.0

# Check logs
docker logs -f api-gateway

# Stop container
docker stop api-gateway
```

### Configuration for Docker

When running in Docker, update service URLs in `.env`:

```env
# For Docker communication, use container names or host.docker.internal
USER_SERVICE_URL=http://host.docker.internal:8001
CONTRACT_SERVICE_URL=http://host.docker.internal:8002
ENTITY_SERVICE_URL=http://host.docker.internal:8003
TIMESHEET_SERVICE_URL=http://host.docker.internal:8004

# Or use docker-compose service names
USER_SERVICE_URL=http://user-service:8001
```

## 📝 API Endpoints

### Gateway Routes (Auto-routing)

The gateway automatically routes requests to appropriate services based on path patterns:

| Path Pattern | Service | Behavior |
|---|---|---|
| `/auth/**`, `/user/**`, `/roles/**` | user-management-service | Strips prefix and forwards |
| `/contracts/**` | contract-management-service | Strips prefix and forwards |
| `/entity/**` | entity-service | Strips prefix and forwards |
| `/timesheet/**`, `/activity/**` | timesheet-management-service | Strips prefix and forwards |

**Example:**
```
GET /user/profile
  ↓ (Gateway)
GET http://user-service:8001/profile
```

### Actuator Endpoints

#### Health Check

```bash
GET /actuator/health

Response:
{
  "status": "UP",
  "service": "gateway-service",
  "timestamp": "2024-01-15T10:30:00.000Z",
  "version": "1.0.0"
}
```

#### Service Info

```bash
GET /actuator/info

Response:
{
  "name": "gateway-service",
  "port": 8000,
  "environment": "local",
  "timestamp": "2024-01-15T10:30:00.000Z"
}
```

### API Documentation

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI Schema**: `http://localhost:8000/openapi.json`

## 🔐 Authentication

### JWT Token Validation

The gateway validates JWT tokens for protected routes:

1. **Request** arrives with `Authorization: Bearer <token>`
2. **Token validation** using configured JWT secret
3. **Claims extraction** - User ID and Role from token
4. **Claim injection** - Headers added to downstream request:
   - `X-User-ID` - User identifier
   - `X-User-Role` - User role
   - `X-Correlation-ID` - Request tracking ID

### Public Routes (No Authentication Required)

```
/auth/login
/user/register
/user/registerUserList
/user/setpassword
/user/updatepassword
/user/forgetpassword
/user
/entity/logo
/entity/logothumbnail
/entityID
```

All other routes require a valid JWT token in the Authorization header.

### Example Protected Request

```bash
curl -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
     http://localhost:8000/user/profile
```

## 🔧 Configuration

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SERVER_PORT` | 8000 | Port to listen on |
| `SERVER_HOST` | 0.0.0.0 | Host to bind to |
| `ENVIRONMENT` | local | Deployment environment |
| `JWT_SECRET` | [long key] | JWT signing/verification secret |
| `JWT_ALGORITHM` | HS256 | JWT algorithm |
| `USER_SERVICE_URL` | http://localhost:8001 | User service URL |
| `CONTRACT_SERVICE_URL` | http://localhost:8002 | Contract service URL |
| `ENTITY_SERVICE_URL` | http://localhost:8003 | Entity service URL |
| `TIMESHEET_SERVICE_URL` | http://localhost:8004 | Timesheet service URL |
| `LOG_LEVEL` | INFO | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `REQUEST_TIMEOUT_SECONDS` | 30 | Gateway request timeout |
| `CORS_ORIGINS` | * | Allowed CORS origins |
| `CORS_CREDENTIALS` | true | Allow credentials in CORS |
| `CORS_METHODS` | GET,POST,PUT,DELETE,OPTIONS | Allowed HTTP methods |
| `CORS_HEADERS` | * | Allowed headers |
| `EUREKA_ENABLED` | true | Enable Eureka service discovery |
| `EUREKA_SERVER_URL` | http://localhost:8761/eureka/ | Eureka server URL |

### JWT Secret Configuration

⚠️ **Security Note**: The default JWT secret is for development only.

For production:

1. Generate a secure secret:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. Update `.env`:
   ```env
   JWT_SECRET=your-secure-secret-key-here
   ```

3. Share the same secret with your authentication service.

## 📊 Logging

### Log Levels

Configure logging detail with `LOG_LEVEL`:

- **DEBUG** - Detailed diagnostic information
- **INFO** - General information about application flow
- **WARNING** - Warning messages for potentially problematic situations
- **ERROR** - Error messages for failures

### Correlation IDs

Each request gets a unique correlation ID for tracing:

```
X-Correlation-ID: 550e8400-e29b-41d4-a716-446655440000
```

The correlation ID is:
- Generated if not provided in request
- Propagated through all service calls
- Included in all logs
- Returned in response headers

## 🔍 Monitoring

### Health Checks

Docker health check is configured:

```bash
curl http://localhost:8000/actuator/health
```

### Request/Response Logging

All requests and responses are logged with:
- Request ID
- HTTP method and path
- Response status code
- Response time
- Correlation ID

### Metrics

Access metrics endpoint:

```bash
curl http://localhost:8000/metrics
```

## 🧪 Testing

### Test Gateway Routing

```bash
# Test user service route
curl http://localhost:8000/user/profile \
  -H "Authorization: Bearer <valid-token>"

# Test contract service route
curl http://localhost:8000/contracts/list \
  -H "Authorization: Bearer <valid-token>"

# Test public endpoint (no auth required)
curl http://localhost:8000/auth/login \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"username": "user", "password": "pass"}'
```

### Verify Middleware

```bash
# Check CORS headers
curl -i -X OPTIONS http://localhost:8000/user/profile

# Check correlation ID in response
curl -i http://localhost:8000/actuator/health | grep X-Correlation-ID

# Test authentication validation
curl http://localhost:8000/user/profile  # Should return 401 without token
```

## 📋 Startup Scripts

### Linux/macOS (`startup.sh`)

```bash
# Start service
./startup.sh start

# Stop service
./startup.sh stop

# Restart service
./startup.sh restart

# Check status
./startup.sh status

# View logs
./startup.sh logs
```

### Windows (`startup.bat`)

```batch
# Start service
startup.bat start

# Stop service
startup.bat stop

# Restart service
startup.bat restart

# Check status
startup.bat status

# View logs
startup.bat logs
```

## 🐛 Troubleshooting

### Port Already in Use

```bash
# Linux/macOS: Kill process on port 8000
lsof -i :8000
kill -9 <PID>

# Windows: Kill process on port 8000
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

### Connection Refused

**Issue**: Cannot connect to upstream services

**Solution**: Verify service URLs in `.env`:

```bash
# Test connectivity
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health
curl http://localhost:8004/health
```

### JWT Token Issues

**Issue**: `Authorization header is invalid`

**Solution**: 
- Verify token format: `Authorization: Bearer <token>`
- Ensure token is not expired
- Verify JWT secret matches between services

### Docker Container Won't Start

```bash
# Check logs
docker logs api-gateway

# Verify environment variables
docker run --rm api-gateway-service:1.0 env | grep SERVER

# Check ports
docker ps | grep api-gateway
```

## 🔄 Migration from Spring Boot

### Key Changes

| Spring Boot | FastAPI | Notes |
|---|---|---|
| `@SpringBootApplication` | FastAPI() | Application initialization |
| `@RestController` | APIRouter | Route handlers |
| `@GlobalFilter` | Middleware | Request/response processing |
| `@Configuration` | Pydantic Settings | Configuration management |
| `application.yml` | `.env` + `config.py` | Environment configuration |
| Servlet Filters | FastAPI Middleware | Request filtering |
| `gateway.routes` | `GATEWAY_ROUTES` config | Route definitions |
| RewritePath filter | Path rewriting logic | URL path manipulation |
| JWT validation | `JwtUtil` class | Token validation |

### Preserved Functionality

✅ API Gateway routing
✅ JWT authentication
✅ CORS handling
✅ Request/response filtering
✅ Service discovery (Eureka compatible)
✅ Health checks
✅ Logging and monitoring
✅ Header manipulation
✅ Error handling

## 📚 Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Uvicorn Documentation](https://www.uvicorn.org/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [httpx Documentation](https://www.python-httpx.org/)
- [JWT.io](https://jwt.io/)

## 📝 License

This project is part of the TimeSmart AI system.

## 🤝 Support

For issues or questions:

1. Check the troubleshooting section
2. Review logs: `./scripts/start_gateway.sh logs`
3. Check configuration: `cat .env`
4. Verify service connectivity

## 📦 Version History

### 1.0.0 (Current)
- Complete Spring Boot to FastAPI conversion
- Full API Gateway functionality
- JWT authentication
- CORS support
- Docker containerization
- Service discovery ready

---

**Last Updated**: December 2024
**Python Version**: 3.11+
**FastAPI Version**: 0.104.1
