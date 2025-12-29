# API Gateway Configuration Examples

## Development Configuration (.env.dev)

```env
# Server Configuration
SERVER_PORT=8000
SERVER_HOST=0.0.0.0
ENVIRONMENT=local
APP_NAME=gateway-service

# Logging
LOG_LEVEL=DEBUG

# Upstream Services (Local)
USER_SERVICE_URL=http://localhost:8001
CONTRACT_SERVICE_URL=http://localhost:8002
ENTITY_SERVICE_URL=http://localhost:8003
TIMESHEET_SERVICE_URL=http://localhost:8004

# CORS Configuration (Permissive for Development)
CORS_ORIGINS=*
CORS_CREDENTIALS=true
CORS_METHODS=GET,POST,PUT,DELETE,PATCH,OPTIONS,HEAD
CORS_HEADERS=*

# Request Timeout
REQUEST_TIMEOUT_SECONDS=30

# JWT Configuration
JWT_SECRET=dev-secret-key-change-in-production
JWT_ALGORITHM=HS256

# Eureka (Optional)
EUREKA_ENABLED=false
EUREKA_SERVER_URL=http://localhost:8761/eureka/
EUREKA_APP_NAME=gateway-service

# Actuator
ACTUATOR_ENABLED=true

# Tracing
ZIPKIN_ENABLED=false
ZIPKIN_URL=http://localhost:9411/api/v2/spans
```

## Staging Configuration (.env.staging)

```env
# Server Configuration
SERVER_PORT=8000
SERVER_HOST=0.0.0.0
ENVIRONMENT=staging
APP_NAME=gateway-service

# Logging
LOG_LEVEL=INFO

# Upstream Services (Staging)
USER_SERVICE_URL=http://user-service-staging:8001
CONTRACT_SERVICE_URL=http://contract-service-staging:8002
ENTITY_SERVICE_URL=http://entity-service-staging:8003
TIMESHEET_SERVICE_URL=http://timesheet-service-staging:8004

# CORS Configuration (More Restrictive)
CORS_ORIGINS=https://staging.timesmart.io,https://smmc-io-staging.timesmart.io
CORS_CREDENTIALS=true
CORS_METHODS=GET,POST,PUT,DELETE,PATCH,OPTIONS
CORS_HEADERS=Authorization,Content-Type,X-Correlation-ID

# Request Timeout
REQUEST_TIMEOUT_SECONDS=30

# JWT Configuration
JWT_SECRET=staging-secret-key-change-immediately
JWT_ALGORITHM=HS256

# Eureka
EUREKA_ENABLED=true
EUREKA_SERVER_URL=http://eureka-staging:8761/eureka/
EUREKA_APP_NAME=gateway-service

# Actuator
ACTUATOR_ENABLED=true

# Tracing
ZIPKIN_ENABLED=true
ZIPKIN_URL=http://zipkin-staging:9411/api/v2/spans
```

## Production Configuration (.env.prod)

```env
# Server Configuration
SERVER_PORT=8000
SERVER_HOST=0.0.0.0
ENVIRONMENT=production
APP_NAME=gateway-service

# Logging
LOG_LEVEL=WARNING

# Upstream Services (Production)
USER_SERVICE_URL=http://user-service:8001
CONTRACT_SERVICE_URL=http://contract-service:8002
ENTITY_SERVICE_URL=http://entity-service:8003
TIMESHEET_SERVICE_URL=http://timesheet-service:8004

# CORS Configuration (Restricted)
CORS_ORIGINS=https://smmc-io-prod.timesmart.io,https://timesmart.io
CORS_CREDENTIALS=true
CORS_METHODS=GET,POST,PUT,DELETE,PATCH,OPTIONS
CORS_HEADERS=Authorization,Content-Type,X-Correlation-ID,X-Request-ID

# Request Timeout
REQUEST_TIMEOUT_SECONDS=30

# JWT Configuration (Use Environment Variable Injection)
JWT_SECRET=${JWT_SECRET}
JWT_ALGORITHM=HS256

# Eureka
EUREKA_ENABLED=true
EUREKA_SERVER_URL=http://eureka-prod:8761/eureka/
EUREKA_APP_NAME=gateway-service

# Actuator
ACTUATOR_ENABLED=false

# Tracing
ZIPKIN_ENABLED=true
ZIPKIN_URL=http://zipkin-prod:9411/api/v2/spans
```

## Docker Deployment (.env.docker)

```env
# Server Configuration
SERVER_PORT=8000
SERVER_HOST=0.0.0.0
ENVIRONMENT=docker
APP_NAME=gateway-service

# Logging
LOG_LEVEL=INFO

# Upstream Services (Docker Network)
USER_SERVICE_URL=http://user-service:8001
CONTRACT_SERVICE_URL=http://contract-service:8002
ENTITY_SERVICE_URL=http://entity-service:8003
TIMESHEET_SERVICE_URL=http://timesheet-service:8004

# CORS Configuration
CORS_ORIGINS=*
CORS_CREDENTIALS=true
CORS_METHODS=GET,POST,PUT,DELETE,PATCH,OPTIONS
CORS_HEADERS=*

# Request Timeout
REQUEST_TIMEOUT_SECONDS=30

# JWT Configuration
JWT_SECRET=docker-secret-key
JWT_ALGORITHM=HS256

# Eureka
EUREKA_ENABLED=true
EUREKA_SERVER_URL=http://eureka:8761/eureka/
EUREKA_APP_NAME=gateway-service

# Actuator
ACTUATOR_ENABLED=true

# Tracing
ZIPKIN_ENABLED=true
ZIPKIN_URL=http://zipkin:9411/api/v2/spans
```

## Kubernetes Configuration

### ConfigMap (config.yaml)
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: gateway-config
  namespace: production
data:
  ENVIRONMENT: "kubernetes"
  SERVER_PORT: "8000"
  SERVER_HOST: "0.0.0.0"
  LOG_LEVEL: "INFO"
  
  # Service Discovery via Kubernetes DNS
  USER_SERVICE_URL: "http://user-service:8001"
  CONTRACT_SERVICE_URL: "http://contract-service:8002"
  ENTITY_SERVICE_URL: "http://entity-service:8003"
  TIMESHEET_SERVICE_URL: "http://timesheet-service:8004"
  
  # CORS
  CORS_ORIGINS: "https://smmc-io-prod.timesmart.io"
  CORS_CREDENTIALS: "true"
  CORS_METHODS: "GET,POST,PUT,DELETE,PATCH,OPTIONS"
  CORS_HEADERS: "Authorization,Content-Type,X-Correlation-ID"
  
  # Timeouts
  REQUEST_TIMEOUT_SECONDS: "30"
  
  # JWT
  JWT_ALGORITHM: "HS256"
  
  # Service Registry
  EUREKA_ENABLED: "false"
  
  # Actuator
  ACTUATOR_ENABLED: "true"
  
  # Tracing
  ZIPKIN_ENABLED: "true"
  ZIPKIN_URL: "http://zipkin:9411/api/v2/spans"
```

### Secret (secret.yaml)
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: gateway-secrets
  namespace: production
type: Opaque
stringData:
  JWT_SECRET: "your-secret-key-here-use-strong-key"
```

### Deployment (deployment.yaml)
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-gateway
  namespace: production
spec:
  replicas: 3
  selector:
    matchLabels:
      app: api-gateway
  template:
    metadata:
      labels:
        app: api-gateway
    spec:
      containers:
      - name: gateway
        image: your-registry/api-gateway:1.0.0
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: gateway-config
        - secretRef:
            name: gateway-secrets
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
```

## Service Configuration Mapping

### Service Routing Reference

```yaml
Services:
  UserManagementService:
    Port: 8001
    URL: http://localhost:8001
    PathPrefixes:
      - /user-management-service
      - /auth
      - /user
      - /roles
    PathRewriting:
      /user-management-service/api/users → /api/users
      /auth/login → /login
      /user/profile → /profile
      /roles/all → /all

  ContractManagementService:
    Port: 8002
    URL: http://localhost:8002
    PathPrefixes:
      - /contract-managment-service
      - /contract-management-service
      - /contracts
    PathRewriting:
      /contract-managment-service/v1/contracts → /v1/contracts
      /contracts/list → /list
      /contract-management-service/details → /details

  EntityService:
    Port: 8003
    URL: http://localhost:8003
    PathPrefixes:
      - /entity-service
      - /entity
      - /app/entitySitePortal
    PathRewriting:
      /entity-service/api/entities → /api/entities
      /entity/search → /search
      /app/entitySitePortal/portal → /portal

  TimesheetManagementService:
    Port: 8004
    URL: http://localhost:8004
    PathPrefixes:
      - /timesheet-management-service
      - /timesheet
      - /activity
    PathRewriting:
      /timesheet-management-service/entries → /entries
      /timesheet/user/123 → /user/123
      /activity/log → /log
```

## Load Testing Configuration

### Locust (load_test.py)
```python
from locust import HttpUser, task, between
import random

class GatewayUser(HttpUser):
    wait_time = between(1, 5)
    
    @task(3)
    def health_check(self):
        self.client.get("/health")
    
    @task(2)
    def list_users(self):
        self.client.get("/user-management-service/api/users")
    
    @task(2)
    def list_contracts(self):
        self.client.get("/contract-managment-service/v1/contracts")
    
    @task(1)
    def create_user(self):
        self.client.post(
            "/user-management-service/api/users",
            json={
                "username": f"user{random.randint(1, 1000)}",
                "email": f"user{random.randint(1, 1000)}@example.com"
            }
        )
```

Run load test:
```bash
locust -f load_test.py --host=http://localhost:8000
```

## Monitoring Configuration

### Prometheus Metrics (Optional Addition)

```python
# In app/main.py
from prometheus_client import Counter, Histogram, generate_latest
import time

# Define metrics
request_count = Counter(
    'gateway_requests_total',
    'Total requests',
    ['method', 'endpoint', 'status']
)

request_duration = Histogram(
    'gateway_request_duration_seconds',
    'Request duration',
    ['method', 'endpoint']
)

# Add metrics endpoint
@app.get("/metrics")
async def metrics():
    return Response(
        generate_latest(),
        media_type="text/plain"
    )
```

Access metrics:
```bash
curl http://localhost:8000/metrics
```

---

**Configuration Files Location**: `./` (root directory)  
**Load with**: `export $(cat .env.prod | xargs)`  
**Last Updated**: December 2025
