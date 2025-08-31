"""Integration tests for metrics functionality."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from app.app import app
from app.metrics import metrics


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def reset_metrics():
    """Reset metrics before each test."""
    # Clear metrics by creating a new instance
    metrics.metrics.clear()
    yield
    # Clean up after test
    metrics.metrics.clear()


class TestMetricsIntegration:
    """Integration tests for metrics collection and endpoint."""

    def test_metrics_endpoint_returns_empty_metrics(self, client):
        """Test that metrics endpoint returns empty metrics initially."""
        response = client.get("/metrics")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] is True
        assert data["message"] == "Metrics retrieved successfully"
        assert "timestamp" in data
        assert data["metrics"] == {}

    def test_metrics_endpoint_after_successful_auth(self, client):
        """Test that metrics are collected after successful authentication."""
        # Mock successful authentication
        with patch("app.app.pesu_academy.authenticate") as mock_auth:
            mock_auth.return_value = {
                "status": True,
                "message": "Login successful",
            }
            
            # Make authentication request
            auth_response = client.post("/authenticate", json={
                "username": "testuser",
                "password": "testpass",
                "profile": False
            })
            assert auth_response.status_code == 200
            
            # Check metrics
            metrics_response = client.get("/metrics")
            assert metrics_response.status_code == 200
            
            data = metrics_response.json()
            assert data["metrics"]["auth_success_total"] == 1

    def test_metrics_endpoint_after_authentication_error(self, client):
        """Test that metrics are collected after authentication error."""
        from app.exceptions.authentication import AuthenticationError
        
        with patch("app.app.pesu_academy.authenticate") as mock_auth:
            mock_auth.side_effect = AuthenticationError("Invalid credentials")
            
            # Make authentication request
            auth_response = client.post("/authenticate", json={
                "username": "baduser",
                "password": "badpass",
                "profile": False
            })
            assert auth_response.status_code == 401
            
            # Check metrics
            metrics_response = client.get("/metrics")
            assert metrics_response.status_code == 200
            
            data = metrics_response.json()
            assert data["metrics"]["pesu_academy_error_total"] == 1
            assert data["metrics"]["auth_failure_total"] == 1

    def test_metrics_endpoint_after_validation_error(self, client):
        """Test that metrics are collected after validation error."""
        # Make request with invalid data (missing required fields)
        auth_response = client.post("/authenticate", json={
            "username": "",  # Empty username should cause validation error
            "password": "testpass"
        })
        assert auth_response.status_code == 400
        
        # Check metrics
        metrics_response = client.get("/metrics")
        assert metrics_response.status_code == 200
        
        data = metrics_response.json()
        assert data["metrics"]["validation_error_total"] == 1

    def test_metrics_endpoint_after_csrf_token_error(self, client):
        """Test that metrics are collected after CSRF token error."""
        from app.exceptions.authentication import CSRFTokenError
        
        with patch("app.app.pesu_academy.authenticate") as mock_auth:
            mock_auth.side_effect = CSRFTokenError("CSRF token error")
            
            # Make authentication request
            auth_response = client.post("/authenticate", json={
                "username": "testuser",
                "password": "testpass",
                "profile": False
            })
            assert auth_response.status_code == 502
            
            # Check metrics
            metrics_response = client.get("/metrics")
            assert metrics_response.status_code == 200
            
            data = metrics_response.json()
            assert data["metrics"]["pesu_academy_error_total"] == 1
            assert data["metrics"]["csrf_token_error_total"] == 1

    def test_metrics_endpoint_after_profile_fetch_error(self, client):
        """Test that metrics are collected after profile fetch error."""
        from app.exceptions.authentication import ProfileFetchError
        
        with patch("app.app.pesu_academy.authenticate") as mock_auth:
            mock_auth.side_effect = ProfileFetchError("Profile fetch failed")
            
            # Make authentication request
            auth_response = client.post("/authenticate", json={
                "username": "testuser",
                "password": "testpass",
                "profile": True
            })
            assert auth_response.status_code == 502
            
            # Check metrics
            metrics_response = client.get("/metrics")
            assert metrics_response.status_code == 200
            
            data = metrics_response.json()
            assert data["metrics"]["pesu_academy_error_total"] == 1
            assert data["metrics"]["profile_fetch_error_total"] == 1

    def test_metrics_endpoint_after_profile_parse_error(self, client):
        """Test that metrics are collected after profile parse error."""
        from app.exceptions.authentication import ProfileParseError
        
        with patch("app.app.pesu_academy.authenticate") as mock_auth:
            mock_auth.side_effect = ProfileParseError("Profile parse failed")
            
            # Make authentication request
            auth_response = client.post("/authenticate", json={
                "username": "testuser",
                "password": "testpass",
                "profile": True
            })
            assert auth_response.status_code == 422
            
            # Check metrics
            metrics_response = client.get("/metrics")
            assert metrics_response.status_code == 200
            
            data = metrics_response.json()
            assert data["metrics"]["pesu_academy_error_total"] == 1
            assert data["metrics"]["profile_parse_error_total"] == 1

    def test_metrics_endpoint_after_unhandled_exception(self, client):
        """Test that metrics are collected after unhandled exception."""
        with patch("app.app.pesu_academy.authenticate") as mock_auth:
            mock_auth.side_effect = RuntimeError("Unexpected error")
            
            # Make authentication request
            auth_response = client.post("/authenticate", json={
                "username": "testuser",
                "password": "testpass",
                "profile": False
            })
            assert auth_response.status_code == 500
            
            # Check metrics
            metrics_response = client.get("/metrics")
            assert metrics_response.status_code == 200
            
            data = metrics_response.json()
            assert data["metrics"]["unhandled_exception_total"] == 1

    def test_metrics_accumulate_over_multiple_requests(self, client):
        """Test that metrics accumulate correctly over multiple requests."""
        # Make multiple validation error requests
        for _ in range(3):
            client.post("/authenticate", json={"username": "", "password": "test"})
        
        # Make a successful request
        with patch("app.app.pesu_academy.authenticate") as mock_auth:
            mock_auth.return_value = {"status": True, "message": "Login successful"}
            client.post("/authenticate", json={"username": "test", "password": "test"})
        
        # Make an authentication error request
        with patch("app.app.pesu_academy.authenticate") as mock_auth:
            from app.exceptions.authentication import AuthenticationError
            mock_auth.side_effect = AuthenticationError("Invalid credentials")
            client.post("/authenticate", json={"username": "bad", "password": "bad"})
        
        # Check accumulated metrics
        metrics_response = client.get("/metrics")
        assert metrics_response.status_code == 200
        
        data = metrics_response.json()
        assert data["metrics"]["validation_error_total"] == 3
        assert data["metrics"]["auth_success_total"] == 1
        assert data["metrics"]["pesu_academy_error_total"] == 1
        assert data["metrics"]["auth_failure_total"] == 1

    def test_health_endpoint_not_affecting_metrics(self, client):
        """Test that health endpoint doesn't affect authentication metrics."""
        # Make multiple health requests
        for _ in range(5):
            response = client.get("/health")
            assert response.status_code == 200
        
        # Check that no authentication metrics were recorded
        metrics_response = client.get("/metrics")
        data = metrics_response.json()
        
        # Should only have empty metrics or no auth-related metrics
        auth_metrics = {k: v for k, v in data["metrics"].items() 
                       if "auth" in k or "error" in k}
        assert len(auth_metrics) == 0

    def test_readme_endpoint_not_affecting_metrics(self, client):
        """Test that readme endpoint doesn't affect authentication metrics."""
        # Make readme request
        response = client.get("/readme", follow_redirects=False)
        assert response.status_code == 308
        
        # Check that no authentication metrics were recorded
        metrics_response = client.get("/metrics")
        data = metrics_response.json()
        
        # Should only have empty metrics or no auth-related metrics
        auth_metrics = {k: v for k, v in data["metrics"].items() 
                       if "auth" in k or "error" in k}
        assert len(auth_metrics) == 0
