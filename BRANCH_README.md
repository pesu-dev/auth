# PESUAuth API - Server Rate Limit Branch

This branch introduces several production-ready enhancements to the PESUAuth API, including rate limiting, enhanced monitoring, structured logging, and improved configuration management.

## 🚀 New Features

### 1. **Rate Limiting**
- Configurable rate limits per endpoint
- Redis-backed or in-memory storage
- Graceful fallback when Redis is unavailable
- Custom rate limit headers in responses

### 2. **Enhanced Monitoring**
- **Basic Health Check**: `/health` - Simple health status
- **Detailed Health Check**: `/health/detailed` - Comprehensive system status including external dependencies
- **Prometheus Metrics**: `/metrics` - Application metrics for monitoring
- System resource monitoring (CPU, memory usage)

### 3. **Structured Logging**
- JSON or console logging formats
- Configurable log levels
- Request/response logging middleware
- Correlation IDs for request tracing

### 4. **Configuration Management**
- Environment-based configuration
- Centralized settings management
- Development/production environment support

### 5. **Enhanced Security**
- CORS support with configurable origins
- Request validation improvements
- Better error handling and reporting

## 📊 Monitoring & Metrics

### Health Endpoints

#### Basic Health Check
```bash
GET /health
```
Returns simple health status for load balancers and basic monitoring.

#### Detailed Health Check
```bash
GET /health/detailed
```
Returns comprehensive health information including:
- Application status
- Redis connectivity (if enabled)
- PESU Academy connectivity
- System resource usage

### Metrics Endpoint
```bash
GET /metrics
```
Prometheus-compatible metrics including:
- Request counts by endpoint and status code
- Request duration histograms
- Authentication attempt counters
- CSRF token operation metrics
- Active connection counts
- Profile fetch duration metrics

## ⚙️ Configuration

### Environment Variables

Create a `.env` file based on `.env.template`:

```env
# Application Settings
DEBUG=false
LOG_LEVEL=INFO
LOG_FORMAT=json

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_AUTHENTICATE=20/minute
RATE_LIMIT_HEALTH=60/minute

# Redis (optional)
REDIS_ENABLED=false
REDIS_URL=redis://localhost:6379

# CORS
CORS_ENABLED=true
CORS_ALLOW_ORIGINS=["*"]

# Monitoring
METRICS_ENABLED=true
```

### Rate Limiting Configuration

Default rate limits:
- **Authentication**: 20 requests per minute per IP
- **Health checks**: 60 requests per minute per IP
- **General endpoints**: 100 requests per hour per IP

## 🐳 Docker Support

The enhanced API maintains full Docker compatibility:

```bash
# Build
docker build -t pesu-auth:rate-limit .

# Run with environment variables
docker run -e REDIS_ENABLED=false -e LOG_FORMAT=console -p 5000:5000 pesu-auth:rate-limit
```

## 🔧 Development

### Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment for development
export DEBUG=true
export LOG_FORMAT=console

# Run the application
python -m app.app --debug
```

### Testing

```bash
# Run all tests including new feature tests
pytest

# Run only the new feature tests
pytest tests/integration/test_new_features.py
```

## 📈 Production Deployment

### Recommended Configuration

```env
DEBUG=false
LOG_LEVEL=INFO
LOG_FORMAT=json
RATE_LIMIT_ENABLED=true
REDIS_ENABLED=true
REDIS_URL=redis://your-redis-server:6379
METRICS_ENABLED=true
CORS_ALLOW_ORIGINS=["https://yourdomain.com"]
```

### Monitoring Setup

1. **Prometheus**: Scrape `/metrics` endpoint
2. **Health Checks**: Monitor `/health` for uptime
3. **Detailed Health**: Monitor `/health/detailed` for comprehensive status
4. **Logs**: Collect structured JSON logs for analysis

### Redis Setup (Optional)

Redis is used for:
- Rate limiting storage (distributed rate limiting)
- Future caching features

If Redis is unavailable, the API falls back to in-memory rate limiting.

## 🔄 Backwards Compatibility

All existing API endpoints and functionality remain unchanged:
- `/authenticate` - Same request/response format
- `/readme` - Same redirect functionality  
- `/` - Same OpenAPI documentation

## 🚨 Breaking Changes

**None** - This branch maintains full backwards compatibility with the existing API.

## 🔍 New Response Headers

Rate-limited endpoints now include headers:
- `X-RateLimit-Limit`: Rate limit threshold
- `X-RateLimit-Remaining`: Remaining requests
- `X-RateLimit-Reset`: Reset time
- `Retry-After`: Seconds to wait when rate limited

## 📊 Metrics Available

- `pesu_auth_requests_total` - Total HTTP requests
- `pesu_auth_request_duration_seconds` - Request duration
- `pesu_auth_authentication_attempts_total` - Authentication attempts
- `pesu_auth_csrf_operations_total` - CSRF token operations
- `pesu_auth_active_connections` - Active HTTP connections
- `pesu_auth_pesu_academy_requests_total` - Requests to PESU Academy
- `pesu_auth_profile_fetch_duration_seconds` - Profile fetch times

## 🛠 Migration from Main Branch

1. Update dependencies: `pip install -r requirements.txt`
2. Copy `.env.template` to `.env` and configure
3. No code changes required for existing clients
4. Optionally set up Redis for better rate limiting
5. Configure monitoring to scrape `/metrics`

---

This enhanced version provides production-ready monitoring, rate limiting, and observability while maintaining full compatibility with existing integrations.
