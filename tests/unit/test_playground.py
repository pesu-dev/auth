"""Tests for the documentation UI without altering API behavior."""

from fastapi.testclient import TestClient

from app.app import app
from app.playground import PLAYGROUND_HTML


def test_explorer_replaces_only_swagger():
    """The root serves HTML while the existing documentation contract remains available."""
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert response.text == PLAYGROUND_HTML
        spec = client.get("/openapi.json").json()
        assert set(spec["paths"]) == {"/authenticate", "/readme", "/health", "/metrics"}
        assert spec["paths"]["/metrics"]["get"]["security"] == [{"MetricsToken": []}]
        assert client.get("/redoc").status_code == 200


def test_request_only_controls():
    """The explorer has no token editor, gateway, or duplicate example heading."""
    assert 'id="authWrap"' not in PLAYGROUND_HTML
    assert 'id="noAuth"' not in PLAYGROUND_HTML
    assert "headers.Authorization" not in PLAYGROUND_HTML
    assert "lovable" not in PLAYGROUND_HTML.lower()
    assert "—" not in PLAYGROUND_HTML.replace('.replaceAll("—", ",")', "")
    assert "### Example request" not in PLAYGROUND_HTML
    assert 'id="reloadBtn"' in PLAYGROUND_HTML
    assert 'id="dotGrid"' in PLAYGROUND_HTML
    