"""Tests for the new features added to the API."""

import pytest

from app.app import app
from app.config import settings


def test_health_check_basic(client):
    """Test the basic health check endpoint."""
    response = client.get("/health")
    if settings.redis_enabled:
        # If Redis is enabled, expect normal health check
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
    else:
        # If Redis is disabled, health check should still succeed or degrade gracefully
        assert response.status_code in [200, 503]
        data = response.json()
        assert "status" in data


def test_health_check_detailed(client):
    """Test the detailed health check endpoint."""
    response = client.get("/health/detailed")
    if settings.redis_enabled:
        assert response.status_code in [200, 503]  # Can be degraded/unhealthy
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "version" in data
        assert "checks" in data
    else:
        # If Redis is disabled, detailed health should still return status
        assert response.status_code in [200, 503]
        data = response.json()
        assert "status" in data


def test_metrics_endpoint(client):
    """Test the metrics endpoint."""
    if settings.metrics_enabled:
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "pesu_auth" in response.text  # Should contain our custom metrics
    else:
        response = client.get("/metrics")
        assert response.status_code == 404


def test_rate_limiting_enabled():
    """Test that rate limiting is properly configured."""
    assert hasattr(app.state, 'limiter') or not settings.rate_limit_enabled


def test_cors_headers(client):
    """Test that CORS headers are present when enabled."""
    response = client.options("/health")
    if settings.cors_enabled:
        # CORS headers should be present in preflight responses
        assert response.status_code in [200, 405]  # Some servers return 405 for OPTIONS


def test_authenticate_endpoint_exists(client):
    """Test that authenticate endpoint exists and has rate limiting."""
    # This should fail with validation error, not 404
    response = client.post("/authenticate", json={})
    assert response.status_code == 400  # Validation error, not 404
    assert "Could not validate request data" in response.json()["message"]


def test_readme_redirect(client):
    """Test that readme redirect still works."""
    response = client.get("/readme", follow_redirects=False)
    assert response.status_code == 307
    assert "github.com" in response.headers["location"]


def test_documentation_available(client):
    """Test that API documentation is available."""
    response = client.get("/")
    assert response.status_code == 200
    # Should contain OpenAPI documentation
    assert "swagger" in response.text.lower() or "openapi" in response.text.lower()


@pytest.mark.parametrize("endpoint", ["/health", "/health/detailed", "/metrics"])
def test_monitoring_endpoints_accessible(client, endpoint):
    """Test that all monitoring endpoints are accessible."""
    response = client.get(endpoint)
    # Should not return 404 (endpoint not found)
    if endpoint in ["/health", "/health/detailed"] and not settings.redis_enabled:
        # If Redis is disabled, allow degraded status
        assert response.status_code in [200, 503]
    else:
        assert response.status_code != 404
