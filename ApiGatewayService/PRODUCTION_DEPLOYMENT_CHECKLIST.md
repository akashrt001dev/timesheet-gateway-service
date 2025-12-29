# Production Deployment Checklist

## Pre-Deployment ✓

### Code Quality
- [x] All HTTP methods supported (GET, POST, PUT, PATCH, DELETE, OPTIONS, HEAD)
- [x] Reusable proxy_request() helper function
- [x] No hardcoded per-method logic
- [x] Comprehensive error handling
- [x] Full type hints
- [x] Detailed docstrings
- [x] Production logging setup
- [x] Configuration via environment variables

### Testing
- [ ] Unit tests for routing logic
- [ ] Integration tests with mock upstream services
- [ ] Load testing (k6, Apache Bench, or Locust)
- [ ] Manual testing of all service routes
- [ ] CORS testing with frontend URL
- [ ] Error scenario testing
- [ ] Header forwarding verification
- [ ] Query parameter preservation tests
- [ ] Request body forwarding tests

### Documentation
- [x] GATEWAY_IMPLEMENTATION.md - Complete implementation guide
- [x] TESTING_GUIDE.md - Testing procedures and examples
- [x] CONFIG_EXAMPLES.md - Configuration for all environments
- [x] ARCHITECTURE.md - System design and data flow
- [x] QUICK_REFERENCE.md - Quick start and common commands
- [x] IMPLEMENTATION_SUMMARY.md - Feature overview
- [x] This file - Deployment checklist

## Configuration Setup ✓

### Environment Variables
- [ ] Create `.env.production` from template
- [ ] Set all upstream service URLs
  - [ ] `USER_SERVICE_URL=http://...`
  - [ ] `CONTRACT_SERVICE_URL=http://...`
  - [ ] `ENTITY_SERVICE_URL=http://...`
  - [ ] `TIMESHEET_SERVICE_URL=http://...`
- [ ] Configure CORS origins for frontend
  - [ ] `CORS_ORIGINS=https://smmc-io-prod.timesmart.io`
- [ ] Set secure JWT secret
  - [ ] Generate strong JWT_SECRET (use openssl or similar)
  - [ ] Store in secure vault (AWS Secrets Manager, etc.)
- [ ] Set appropriate log level
  - [ ] `LOG_LEVEL=WARNING` for production
- [ ] Configure request timeout
  - [ ] `REQUEST_TIMEOUT_SECONDS=30` (or appropriate value)
- [ ] Set environment
  - [ ] `ENVIRONMENT=production`

### Upstream Services
- [ ] Verify all upstream services are running and accessible
- [ ] Document each upstream service:
  - [ ] Service name
  - [ ] Port number
  - [ ] Health check endpoint
  - [ ] Expected response time
- [ ] Test direct connectivity to each upstream service
  ```bash
  curl http://localhost:8001/health
  curl http://localhost:8002/health
  curl http://localhost:8003/health
  curl http://localhost:8004/health
  ```

## Docker/Container Setup

### Docker
- [ ] Review Dockerfile
- [ ] Build image
  ```bash
  docker build -t api-gateway:1.0.0 .
  ```
- [ ] Test container locally
  ```bash
  docker run -p 8000:8000 --env-file .env.production api-gateway:1.0.0
  ```
- [ ] Push to registry
  ```bash
  docker tag api-gateway:1.0.0 your-registry/api-gateway:1.0.0
  docker push your-registry/api-gateway:1.0.0
  ```

### Docker Compose
- [ ] Update docker-compose.yml with actual service endpoints
- [ ] Test with `docker-compose up`
- [ ] Verify all services start correctly

### Kubernetes
- [ ] Create ConfigMap for non-sensitive configuration
- [ ] Create Secret for JWT_SECRET
- [ ] Create Deployment with:
  - [ ] Correct image URL
  - [ ] Resource requests and limits
  - [ ] Health check probes (liveness, readiness)
  - [ ] Environment variables from ConfigMap/Secret
- [ ] Create Service for load balancing
- [ ] Create Ingress for external access
- [ ] Deploy and verify

## Network & Security ✓

### Network Configuration
- [ ] Gateway accessible on port 8000
- [ ] All upstream services accessible from gateway
- [ ] Network policies configured (if using Kubernetes)
- [ ] Firewall rules allow gateway traffic

### Security
- [ ] HTTPS/TLS enabled in front of gateway (via reverse proxy like nginx)
- [ ] JWT validation enabled
- [ ] CORS configured appropriately (not `*` in production)
- [ ] Sensitive headers filtered
- [ ] Request body size limits configured
- [ ] Rate limiting implemented (if needed)

### SSL/TLS
- [ ] Obtain SSL certificate for gateway domain
- [ ] Configure nginx/load balancer for HTTPS
- [ ] Redirect HTTP to HTTPS
- [ ] Test HTTPS connection

## Monitoring & Logging

### Logging
- [ ] Centralized log collection configured
  - [ ] ELK Stack
  - [ ] CloudWatch
  - [ ] Datadog
  - [ ] Splunk
  - [ ] Other: ___________
- [ ] Log retention policy configured
- [ ] Log rotation configured
- [ ] Correlation ID logging enabled
- [ ] Test logging with actual requests

### Monitoring
- [ ] Prometheus metrics endpoint exposed (optional)
- [ ] APM configured (optional)
  - [ ] New Relic
  - [ ] DataDog
  - [ ] Splunk APM
  - [ ] Jaeger
  - [ ] Other: ___________
- [ ] Dashboards created:
  - [ ] Request rate
  - [ ] Error rate
  - [ ] Response time (p50, p95, p99)
  - [ ] Upstream service health
- [ ] Alerts configured for:
  - [ ] High error rate (>5%)
  - [ ] High latency (>1000ms)
  - [ ] Upstream service unavailable (503, 504)
  - [ ] Gateway down

### Health Checks
- [ ] Health check endpoint configured in load balancer
  - [ ] Endpoint: `/health`
  - [ ] Interval: 10-30 seconds
  - [ ] Timeout: 5 seconds
  - [ ] Unhealthy threshold: 3
- [ ] Readiness check works before accepting traffic
- [ ] Liveness check detects when to restart

## Load Balancing

### Setup
- [ ] Load balancer (nginx, AWS ELB, etc.) configured
- [ ] Multiple gateway instances deployed (minimum 2 for HA)
- [ ] Health check configured on load balancer
- [ ] Session affinity configured if needed
- [ ] SSL termination at load balancer

### Testing
- [ ] Test load balancing with multiple instances
- [ ] Verify requests distribute evenly
- [ ] Test failover (stop one instance, verify requests route to others)
- [ ] Load test with full expected traffic

## Capacity Planning

### Resource Allocation
- [ ] CPU: Minimum 1 core, recommended 2+ cores per instance
- [ ] Memory: Minimum 512MB, recommended 1GB+ per instance
- [ ] Disk: 1GB minimum for logs
- [ ] Network: Bandwidth adequate for expected load

### Autoscaling
- [ ] Auto-scaling policy configured (if using Kubernetes/ECS)
- [ ] Scale-up threshold: e.g., CPU >70%
- [ ] Scale-down threshold: e.g., CPU <20%
- [ ] Min replicas: 2 (for HA)
- [ ] Max replicas: appropriate for expected load
- [ ] Scale-up cooldown: 2-3 minutes
- [ ] Scale-down cooldown: 5-10 minutes

## Performance Tuning

### Connection Pooling
- [x] httpx connection pooling enabled in code
- [ ] Connection pool size: 100 (default, adjust if needed)
- [ ] Keep-alive connections enabled
- [ ] Connection timeout: appropriate for network

### Request Handling
- [x] Streaming responses enabled (memory efficient)
- [x] Async/await used throughout
- [ ] Request timeout: 30 seconds (verify appropriate)
- [ ] Body size limits: configured if needed

### Upstream Services
- [ ] Connection pooling to upstream services
- [ ] Appropriate timeouts for upstream services
- [ ] Circuit breaker pattern (optional, for resilience)
- [ ] Retry logic (optional, with exponential backoff)

## Backup & Disaster Recovery

### Configuration Backup
- [ ] .env.production backed up securely
- [ ] Environment variables backed up
- [ ] Gateway configuration version controlled
- [ ] Docker image versions tagged and archived

### Disaster Recovery
- [ ] RTO (Recovery Time Objective) defined
- [ ] RPO (Recovery Point Objective) defined
- [ ] Disaster recovery plan documented
- [ ] Regular failover drills performed
- [ ] Backup upstream services configured (if applicable)

## Deployment Day

### Pre-Deployment
- [ ] All team members notified
- [ ] Maintenance window scheduled (if needed)
- [ ] Rollback plan documented and tested
- [ ] Communication channels established
- [ ] On-call support available

### Deployment Steps
1. [ ] Deploy load balancer configuration (if changed)
2. [ ] Deploy gateway container(s)
   ```bash
   docker pull your-registry/api-gateway:1.0.0
   docker run -p 8000:8000 --env-file .env.production api-gateway:1.0.0
   ```
3. [ ] Verify gateway health: `curl http://localhost:8000/health`
4. [ ] Verify upstream services accessible
5. [ ] Test routing for all services
6. [ ] Monitor metrics and logs
7. [ ] Verify no increase in error rate

### Testing (Post-Deployment)
- [ ] Health check passes
- [ ] Can access frontend via root path
- [ ] Can access user service
- [ ] Can access contract service
- [ ] Can access entity service
- [ ] Can access timesheet service
- [ ] Query parameters preserved
- [ ] POST/PUT/PATCH with body work
- [ ] Error responses appropriate
- [ ] CORS headers correct
- [ ] Correlation IDs present in logs

### Monitoring (Post-Deployment)
- [ ] Monitor error rate (should be <1%)
- [ ] Monitor latency (should be <500ms p95)
- [ ] Monitor upstream service responses
- [ ] Check logs for warnings/errors
- [ ] Verify alerts functioning
- [ ] Watch for memory leaks

## Post-Deployment ✓

### Documentation Updates
- [ ] Update deployment documentation
- [ ] Record environment variables (securely)
- [ ] Document any custom configurations
- [ ] Update runbooks
- [ ] Update troubleshooting guides

### Team Communication
- [ ] Notify team of successful deployment
- [ ] Share deployment notes
- [ ] Document any issues encountered and resolutions
- [ ] Update status pages if applicable

### Ongoing Maintenance
- [ ] Schedule regular log review
- [ ] Monitor metrics dashboards daily
- [ ] Plan regular updates/patches
- [ ] Review and optimize based on metrics
- [ ] Conduct post-deployment review meeting

## Rollback Plan

### If Issues Occur
1. [ ] Identify issue (check logs and metrics)
2. [ ] Decide: rollback vs. hotfix
3. [ ] If rollback:
   - [ ] Stop new gateway instances
   - [ ] Revert to previous version
   - [ ] Verify health
   - [ ] Monitor metrics
4. [ ] If hotfix:
   - [ ] Fix issue in code
   - [ ] Build new image
   - [ ] Test locally
   - [ ] Deploy new version
   - [ ] Monitor closely

### Communication
- [ ] Update status page
- [ ] Notify stakeholders
- [ ] Document issue and resolution
- [ ] Post-mortem if major issue

## Success Criteria

✅ **All of the following should be true:**

- [ ] Gateway running without errors
- [ ] All upstream services responding correctly
- [ ] Error rate < 1%
- [ ] P95 latency < 500ms
- [ ] No memory leaks detected
- [ ] All monitoring alerts working
- [ ] Logs being collected and searchable
- [ ] Team confident in solution
- [ ] Ready for scale-up if needed

## Appendix: Command Reference

### Kubernetes Deployment
```bash
# Apply ConfigMap
kubectl apply -f configmap.yaml

# Apply Secret
kubectl apply -f secret.yaml

# Deploy
kubectl apply -f deployment.yaml

# Check status
kubectl get pods -l app=api-gateway
kubectl logs -l app=api-gateway

# Scale
kubectl scale deployment api-gateway --replicas=3

# Rollout update
kubectl set image deployment/api-gateway \
  gateway=your-registry/api-gateway:1.0.1

# Rollback
kubectl rollout undo deployment/api-gateway
```

### Docker Deployment
```bash
# Build
docker build -t api-gateway:1.0.0 .

# Tag
docker tag api-gateway:1.0.0 your-registry/api-gateway:1.0.0

# Push
docker push your-registry/api-gateway:1.0.0

# Run
docker run -d \
  --name api-gateway \
  -p 8000:8000 \
  --env-file .env.production \
  your-registry/api-gateway:1.0.0

# Logs
docker logs -f api-gateway

# Stop
docker stop api-gateway

# Remove
docker rm api-gateway
```

### Testing
```bash
# Health check
curl http://localhost:8000/health

# Test with verbose output
curl -v http://localhost:8000/user-management-service/api/users

# Test with headers
curl -i http://localhost:8000/health

# Load test
ab -n 10000 -c 100 http://localhost:8000/health
```

---

**Status**: Ready for Production  
**Last Updated**: December 2025  
**Version**: 1.0.0
