# 🚀 Quick Start Guide - FastAPI Gateway Service

## 📍 Location
```
ApiGatewayService/
```

Located next to the original Spring Boot `api-gateway-service` folder.

---

## ⚡ 5-Minute Setup

### Step 1: Navigate to Project
```bash
cd ApiGatewayService
```

### Step 2: Create Environment File
```bash
# Copy example configuration
cp .env.example .env

# Edit with your service URLs (optional for local testing)
# nano .env  (or use your editor)
```

### Step 3: Install Dependencies
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install packages
pip install -r requirements.txt
```

### Step 4: Run the Gateway
```bash
# Start the server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Step 5: Verify It Works
```bash
# In another terminal, test the health endpoint
curl http://localhost:8000/actuator/health

# Should return:
# {
#   "status": "UP",
#   "service": "gateway-service",
#   "timestamp": "2024-01-15T10:30:00.000Z",
#   "version": "1.0.0"
# }
```

---

## 🐳 Docker Setup (3 minutes)

```bash
# Build and run with Docker Compose
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f api-gateway

# Stop
docker-compose down
```

---

## 📖 Documentation Files

After setup, read these in order:

1. **README.md** - Complete guide
2. **CONVERSION_GUIDE.md** - Spring Boot to FastAPI mapping
3. **VERIFICATION_CHECKLIST.md** - Features & quality assurance
4. **.env.example** - All configuration options

---

## 🧪 Test the Gateway

### Test Public Endpoint (No Auth Required)
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "test", "password": "test"}'
```

### Test Protected Endpoint (Requires Token)
```bash
curl http://localhost:8000/user/profile \
  -H "Authorization: Bearer your-jwt-token-here"
```

### View API Documentation
```
http://localhost:8000/docs
```

---

## ⚙️ Configuration

### Key Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `SERVER_PORT` | 8000 | Port to listen on |
| `JWT_SECRET` | [preset] | JWT signing key |
| `USER_SERVICE_URL` | http://localhost:8001 | User service URL |
| `LOG_LEVEL` | INFO | Logging level |

See `.env.example` for all options.

---

## 📚 What's Included

✅ **Core Gateway**
- Request routing to 4 microservices
- JWT authentication
- CORS support
- Error handling

✅ **Monitoring**
- Health checks
- Service info endpoint
- Structured logging
- Correlation ID tracking

✅ **Deployment**
- Dockerfile (production-ready)
- Docker Compose
- Startup scripts
- Environment management

✅ **Documentation**
- 1500+ lines of docs
- Configuration guide
- Troubleshooting tips
- Code examples

---

## 🆘 Troubleshooting

### Port Already in Use
```bash
# Linux/macOS
lsof -i :8000
kill -9 <PID>

# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

### Service Connection Failed
1. Check `.env` - verify service URLs
2. Ensure upstream services are running
3. Check logs: `docker-compose logs api-gateway`

### JWT Token Invalid
1. Verify token format: `Authorization: Bearer <token>`
2. Check `JWT_SECRET` matches your auth service
3. Verify token is not expired

---

## 📂 Project Structure

```
ApiGatewayService/
├── app/
│   ├── main.py                 ← FastAPI application
│   ├── api/gateway_routes.py   ← Routing logic
│   ├── core/config.py          ← Configuration
│   ├── core/security.py        ← JWT/Auth
│   ├── services/               ← Gateway forwarding
│   └── filters/                ← Middleware
├── scripts/
│   ├── start_gateway.sh        ← Linux/macOS startup
│   └── start_gateway.bat       ← Windows startup
├── Dockerfile                  ← Docker image
├── docker-compose.yml          ← Full stack setup
├── requirements.txt            ← Dependencies
├── .env                        ← Local configuration
├── README.md                   ← Full documentation
└── CONVERSION_GUIDE.md         ← Spring Boot conversion details
```

---

## 🎯 Common Tasks

### Start with Startup Script
```bash
# Linux/macOS
chmod +x startup.sh
./startup.sh start

# Windows
startup.bat start
```

### View Logs
```bash
# Using script
./startup.sh logs

# Using Docker
docker-compose logs -f api-gateway

# Direct uvicorn output
# Check terminal where you ran uvicorn
```

### Stop the Service
```bash
# Using script
./startup.sh stop

# Using Docker
docker-compose down

# Using Ctrl+C in terminal
# Press Ctrl+C where uvicorn is running
```

---

## 🔍 Verify Installation

After running the gateway, verify these endpoints work:

```bash
# 1. Health Check
curl http://localhost:8000/actuator/health
# Should return: {"status": "UP", ...}

# 2. Service Info
curl http://localhost:8000/actuator/info
# Should return: {"name": "gateway-service", ...}

# 3. API Documentation
# Open in browser: http://localhost:8000/docs
# Should show Swagger UI with all endpoints
```

---

## 📞 Need Help?

1. **Setup Issues?** → See README.md → Troubleshooting
2. **Configuration Questions?** → See .env.example
3. **Understanding Conversion?** → See CONVERSION_GUIDE.md
4. **Feature Checklist?** → See VERIFICATION_CHECKLIST.md

---

## ✨ What's Different from Spring Boot?

✅ **Same Features**
- API Gateway routing
- JWT authentication
- CORS handling
- Error handling
- Health checks

✅ **Easier Setup**
- No Maven/Java needed
- Simple pip install
- Standard Python tools

✅ **Better Documentation**
- Comprehensive README
- Code examples
- Troubleshooting guide

---

## 🎉 Ready to Go!

Your FastAPI Gateway Service is now:
- ✅ Fully converted from Spring Boot
- ✅ Production-ready
- ✅ Documented
- ✅ Tested

**Next Step**: Read [README.md](README.md) for complete documentation.

---

**Last Updated**: December 2024
**Status**: Ready for Use ✨
