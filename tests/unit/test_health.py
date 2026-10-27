"""Tests for /health: the version and environment fields, HEAD, and Cache-Control."""

from importlib.metadata import version

import pytest
from fastapi.testclient import TestClient

from app.app import app


@pytest.fixture()
def client():
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def test_version(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["version"] == version("pesu-auth")


def test_head_method_for_health(client):
    head_response = client.head("/health")
    assert head_response.status_code == 200
    assert head_response.text == ""


def test_get_cache_no_store_header(client):
    get_response = client.get("/health")
    assert get_response.headers.get("Cache-Control") == "no-store"


def test_head_cache_no_store_header(client):
    head_response = client.head("/health")
    assert head_response.headers.get("Cache-Control") == "no-store"


@pytest.mark.parametrize("valid_cases", ("development", "production", "staging"))
def test_valid_cases_for_pesu_auth_environment(monkeypatch, valid_cases):
    monkeypatch.setenv("PESU_AUTH_ENVIRONMENT", valid_cases)
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.json()["environment"] == valid_cases


def test_default_fallback_pesu_auth_environment():
    assert app.state.environment == "development"


@pytest.mark.parametrize("invalid_cases", ("", "prod", "Development"))
def test_invalid_cases_for_pesu_auth_environment(monkeypatch, invalid_cases):
    monkeypatch.setenv("PESU_AUTH_ENVIRONMENT", invalid_cases)
    with pytest.raises(ValueError, match="PESU_AUTH_ENVIRONMENT must be development, staging or production"):
        with TestClient(app):
            pass
