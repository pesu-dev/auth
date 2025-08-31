#129 - Add metrics logging with thread-safe collector and /metrics endpoint

![Feature](https://img.shields.io/badge/Type-New%20Feature-brightgreen)
![Tests](https://img.shields.io/badge/Tests-76%2F76%20Passing-success)
![Coverage](https://img.shields.io/badge/Coverage-Unit%2BIntegration-blue)
![Performance](https://img.shields.io/badge/Performance-Zero%20Impact-green)
![Thread Safety](https://img.shields.io/badge/Thread%20Safety-✅%20Verified-orange)

## 📌 Description

This PR implements comprehensive metrics logging for the PESUAuth API to enable monitoring and observability of authentication requests, errors, and system performance.

**What is the purpose of this PR?**
- Adds a thread-safe metrics collection system to track authentication successes, failures, and various error types
- Implements a new `/metrics` endpoint to expose collected metrics in JSON format
- Integrates metrics tracking throughout the FastAPI application lifecycle

**What problem does it solve?**
- Provides visibility into API usage patterns and authentication success rates
- Enables monitoring of error types and frequencies for better debugging and system health assessment
- Tracks CSRF token refresh operations for background task monitoring
- Facilitates performance analysis and capacity planning

**Background:**
The API previously had no metrics or monitoring capabilities, making it difficult to assess system health, debug issues, or understand usage patterns. This implementation provides comprehensive tracking without impacting performance.

> ℹ️ **Fixes / Related Issues**
> Fixes: #129

## 🧱 Type of Change

- [x] ✨ New feature – Adds functionality without breaking existing APIs
- [x] 📝 Documentation update – README, docstrings, OpenAPI tags, etc.
- [x] 🧪 Test suite change – Adds/updates unit, functional, or integration tests
- [x] 🕵️ Debug/logging enhancement – Adds or improves logging/debug support

## 🧪 How Has This Been Tested?

- [x] Unit Tests (`tests/unit/`)
- [ ] Functional Tests (`tests/functional/`)
- [x] Integration Tests (`tests/integration/`)
- [x] Manual Testing

> ⚙️ **Test Configuration:**
>
> - OS: Windows 11
> - Python: 3.13.2 via uv
> - [x] Docker build tested

**Testing Details:**
- **Unit Tests**: 10 comprehensive tests for MetricsCollector covering thread safety, concurrent access, edge cases, and special character handling
- **Integration Tests**: End-to-end FastAPI testing with mock authentication flows to verify metrics collection in real scenarios
- **Manual Testing**: Live API testing confirmed correct metrics tracking for success/failure scenarios and endpoint functionality

## ✅ Checklist

- [x] My code follows the [CONTRIBUTING.md](https://github.com/pesu-dev/auth/blob/main/.github/CONTRIBUTING.md) guidelines
- [x] I've performed a self-review of my changes
- [x] I've added/updated necessary comments and docstrings
- [x] I've updated relevant docs (README or endpoint docs)
- [x] No new warnings introduced
- [x] I've added tests to cover my changes
- [x] All tests pass locally (`scripts/run_tests.py`) - 
- [x] I've run linting and formatting (`pre-commit run --all-files`) - 
- [x] Docker image builds and runs correctly - 
- [x] Changes are backwards compatible (if applicable)
- [ ] Feature flags or `.env` vars updated (if applicable) - **Not applicable**
- [x] I've tested across multiple environments (if applicable)
- [x] Benchmarks still meet expected performance (`scripts/benchmark_auth.py`) - 

## 🛠️ Affected API Behaviour

- [x] `app/app.py` – Modified `/authenticate` route logic

**New API Endpoint:**
- **`/metrics`** - New GET endpoint that returns current application metrics in JSON format

### 🧩 Models
* [x] `app/models/response.py` – Used existing response model for metrics endpoint formatting

**New Files Added:**
- `app/metrics.py` - Core MetricsCollector implementation with thread-safe operations
- `app/docs/metrics.py` - OpenAPI documentation for the new /metrics endpoint  
- `tests/unit/test_metrics.py` - Comprehensive unit tests for MetricsCollector
- `tests/integration/test_metrics_integration.py` - Integration tests for metrics collection

### 🐳 DevOps & Config

* [ ] `Dockerfile` – No changes to build process
* [ ] `.github/workflows/*.yaml` – No CI/CD pipeline changes required
* [ ] `pyproject.toml` / `requirements.txt` – No new dependencies added
* [ ] `.pre-commit-config.yaml` – No linting or formatting changes

### 📊 Benchmarks & Analysis

* [ ] `scripts/benchmark_auth.py` – No changes to benchmark scripts
* [ ] `scripts/analyze_benchmark.py` – No changes to analysis tools
* [ ] `scripts/run_tests.py` – No changes to test runner

## 📸 Screenshots / API Demos

### 🎯 Metrics Endpoint in Action

![Metrics Endpoint Response](metrics-images/image.png)

*Live metrics collection showing authentication success/failure tracking*

### Metrics Endpoint Response Example
```json
{
  "status": true,
  "message": "Metrics retrieved successfully",
  "timestamp": "2025-08-28T15:30:45.123456+05:30",
  "metrics": {
    "auth_success_total": 150,
    "auth_failure_total": 12,
    "validation_error_total": 8,
    "pesu_academy_error_total": 5,
    "unhandled_exception_total": 0,
    "csrf_token_error_total": 2,
    "profile_fetch_error_total": 1,
    "profile_parse_error_total": 0,
    "csrf_token_refresh_success_total": 45,
    "csrf_token_refresh_failure_total": 1
  }
}
```

### 🔧 Testing Results Dashboard

![Test Results](metrics-images/image-2.png)

*Comprehensive test suite covering unit, integration, and functional scenarios*


### Updated API Endpoints Table
| **Endpoint**    | **Method** | **Description**                                        |
|-----------------|------------|--------------------------------------------------------|
| `/`             | `GET`      | Serves the interactive API documentation (Swagger UI). |
| `/authenticate` | `POST`     | Authenticates a user using their PESU credentials.     |
| `/health`       | `GET`      | A health check endpoint to monitor the API's status.   |
| `/readme`       | `GET`      | Redirects to the project's official GitHub repository. |
| **`/metrics`**  | **`GET`**  | **Returns current application metrics and counters.**   |



**Metrics Tracked:**
1. `auth_success_total` - Successful authentication attempts
2. `auth_failure_total` - Failed authentication attempts  
3. `validation_error_total` - Request validation failures
4. `pesu_academy_error_total` - PESU Academy service errors
5. `unhandled_exception_total` - Unexpected application errors
6. `csrf_token_error_total` - CSRF token extraction failures
7. `profile_fetch_error_total` - Profile page fetch failures
8. `profile_parse_error_total` - Profile parsing errors
9. `csrf_token_refresh_success_total` - Successful background CSRF refreshes
10. `csrf_token_refresh_failure_total` - Failed background CSRF refreshes

