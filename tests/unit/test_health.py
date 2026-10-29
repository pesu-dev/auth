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
    assert get_response.status_code == 200
    assert get_response.headers.get("Cache-Control") == "no-store"


def test_head_cache_no_store_header(client):
    head_response = client.head("/health")
    assert head_response.status_code == 200
    assert head_response.headers.get("Cache-Control") == "no-store"


def test_each_environment_is_reported(monkeypatch, environment):
    monkeypatch.setenv("PESU_AUTH_ENVIRONMENT", environment)
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.json()["environment"] == environment


def test_the_environment_defaults_to_development(monkeypatch):
    monkeypatch.delenv("PESU_AUTH_ENVIRONMENT", raising=False)
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.json()["environment"] == "development"


def test_an_invalid_environment_stops_startup(monkeypatch, invalid_environment):
    monkeypatch.setenv("PESU_AUTH_ENVIRONMENT", invalid_environment)
    with pytest.raises(ValueError, match="PESU_AUTH_ENVIRONMENT must be development, staging or production"):
        with TestClient(app):
            pass
