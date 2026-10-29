"""Tests for the documentation UI without altering API behavior."""

import re
from pathlib import Path

from fastapi.testclient import TestClient

from app.app import app

PLAYGROUND_HTML = (Path(__file__).parents[2] / "app" / "templates" / "playground.html").read_text(encoding="utf-8")


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
        assert client.get("/docs").status_code == 200
        assert client.get("/redoc").status_code == 200


def test_schema_driven_request_controls():
    """Request forms, optional bearer security, and response-only copy are available."""
    assert 'id="requestForm"' in PLAYGROUND_HTML
    assert 'id="authWrap" hidden' in PLAYGROUND_HTML
    token_input = re.search(r'<input[^>]+id="token"[^>]*>', PLAYGROUND_HTML)
    assert token_input and 'type="password"' in token_input.group(0)
    assert "headers.Authorization" in PLAYGROUND_HTML
    assert "securitySchemes" in PLAYGROUND_HTML
    assert 'id="copyRequestBtn"' in PLAYGROUND_HTML
    assert 'id="body"' not in PLAYGROUND_HTML
    assert "Example request</div>" not in PLAYGROUND_HTML
    assert 'id="reloadBtn"' not in PLAYGROUND_HTML
    assert 'id="dotGrid"' in PLAYGROUND_HTML
    assert "List[str]" not in PLAYGROUND_HTML
    assert 'if (name === "fields" ? profileRequested : selected.length)' in PLAYGROUND_HTML
    assert "navigator.clipboard.writeText(state.responseBody)" in PLAYGROUND_HTML
    assert 'id="status" class="status-chip"' in PLAYGROUND_HTML
    assert "function highlightJson" in PLAYGROUND_HTML


def test_profile_fields_default_to_all_selected():
    """With profile requested, every field checkbox starts checked and is sent as chosen."""
    assert 'name === "fields" ? " checked"' in PLAYGROUND_HTML
    assert "profileRequested" in PLAYGROUND_HTML
    assert "syncFields" not in PLAYGROUND_HTML


def test_profile_fields_are_disabled_without_profile_and_reject_empty_selection():
    """The UI prevents an empty selection from silently requesting every field."""
    assert "fieldset.disabled = !enabled" in PLAYGROUND_HTML
    assert "first.setCustomValidity(" in PLAYGROUND_HTML
    assert 'name === "fields" && profileRequested && !selected.length' in PLAYGROUND_HTML
    assert "Select at least one profile field, or set profile to false." in PLAYGROUND_HTML


def test_metrics_documents_optional_header_and_concise_format():
    """Metrics uses an optional Authorization header, not a query token."""
    assert "Bearer token (optional)" in PLAYGROUND_HTML
    assert "Bearer &lt;token&gt;" not in PLAYGROUND_HTML
    assert "Bearer token. Only required when the server sets `METRICS_TOKEN`." in PLAYGROUND_HTML
    assert (
        "Only needed when the server sets <code>METRICS_TOKEN</code>. "
        "Sent in the <code>Authorization</code> header." in PLAYGROUND_HTML
    )
    assert "Response format: Prometheus (default) or JSON." in PLAYGROUND_HTML


def test_theme_options_publish_their_state():
    """Every theme option declares an aria-checked state up front."""
    assert PLAYGROUND_HTML.count("aria-checked=") >= 3
    assert 'b.setAttribute("aria-checked", String(active))' in PLAYGROUND_HTML


def test_the_documentation_entry_is_listed_last():
    """The Explorer lists FastAPI's built-in Swagger UI as the final endpoint."""
    assert '"/docs"' in PLAYGROUND_HTML
    assert "swagger-ui-dist@" in PLAYGROUND_HTML


def test_explorer_document_is_separate_html():
    """The explorer is served from its standalone HTML template."""
    document = Path(__file__).parents[2] / "app" / "templates" / "playground.html"
    assert PLAYGROUND_HTML == document.read_text(encoding="utf-8")


def test_the_navbar_shows_the_api_version_from_the_spec():
    """The version badge is filled from the served OpenAPI spec, not hard-coded."""
    assert '<span id="version" class="version" hidden></span>' in PLAYGROUND_HTML
    assert "state.spec.info?.version" in PLAYGROUND_HTML


def test_the_navbar_has_a_hidden_environment_badge():
    """The environment badge sits right after the version badge and starts hidden."""
    assert (
        '<span id="version" class="version" hidden></span><span id="environment" class="environment" hidden></span>'
        in PLAYGROUND_HTML
    )


def test_the_environment_badge_is_filled_from_health():
    """The environment badge is filled from /health, as text, never as HTML."""
    assert 'fetch("/health", { cache: "no-store" })' in PLAYGROUND_HTML
    assert "health?.environment" in PLAYGROUND_HTML
    assert '$("environment").textContent = environment' in PLAYGROUND_HTML
    assert "innerHTML" not in PLAYGROUND_HTML.split("function loadEnvironment()")[1].split("\n      }\n")[0]


def test_each_environment_has_its_own_colour(environment):
    """Each environment colours the badge with an existing theme token."""
    token = {"production": "--success", "staging": "--warning", "development": "--get"}[environment]
    rule = re.search(rf'\.environment\[data-env="{environment}"\] \{{([^}}]*)\}}', PLAYGROUND_HTML)
    assert rule
    assert f"color: var({token});" in rule.group(1)
    assert f"border-color: var({token});" in rule.group(1)


def test_a_failing_health_does_not_break_the_explorer():
    """/health is fetched apart from the spec, with its own catch, so a failure only leaves the badge hidden."""
    assert "function loadEnvironment()" in PLAYGROUND_HTML
    assert "loadEnvironment" not in PLAYGROUND_HTML.split("async function load()")[1].split("\n      }\n")[0]
    assert ".catch(() => {});" in PLAYGROUND_HTML.split("function loadEnvironment()")[1]
    assert re.search(r"\n\s*load\(\);\n\s*loadEnvironment\(\);\n", PLAYGROUND_HTML)
