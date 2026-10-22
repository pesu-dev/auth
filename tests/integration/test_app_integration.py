import os

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.app import app
from app.exceptions.authentication import AuthenticationError

unhandled_router = APIRouter()


@unhandled_router.get("/raiseUnhandled", include_in_schema=False)
async def raise_unhandled():
    raise RuntimeError("Simulated internal server error")


app.include_router(unhandled_router)


@pytest.fixture(scope="module")
def client():
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.mark.secret_required
def test_integration_authenticate_success_username_email(client):
    payload = {
        "username": os.getenv("TEST_EMAIL"),
        "password": os.getenv("TEST_PASSWORD"),
        "profile": False,
    }

    response = client.post("/authenticate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] is True
    assert "profile" not in data
    assert "timestamp" in data
    assert data["message"] == "Login successful."


@pytest.mark.secret_required
def test_integration_authenticate_success_username_prn(client):
    payload = {
        "username": os.getenv("TEST_PRN"),
        "password": os.getenv("TEST_PASSWORD"),
        "profile": False,
    }

    response = client.post("/authenticate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] is True
    assert "profile" not in data
    assert "timestamp" in data
    assert data["message"] == "Login successful."


@pytest.mark.secret_required
def test_integration_authenticate_success_username_mobile(client):
    payload = {
        "username": os.getenv("TEST_MOBILE"),
        "password": os.getenv("TEST_PASSWORD"),
        "profile": False,
    }

    response = client.post("/authenticate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] is True
    assert "profile" not in data
    assert "timestamp" in data
    assert data["message"] == "Login successful."


@pytest.mark.secret_required
def test_integration_authenticate_success_username_srn(client):
    payload = {"username": os.getenv("TEST_SRN"), "password": os.getenv("TEST_PASSWORD")}

    response = client.post("/authenticate", json=payload)
    assert response.status_code == 200
    assert response.json()["message"] == "Login successful."


@pytest.mark.secret_required
def test_integration_authenticate_with_specific_profile_fields(client, check_live_fields, specific_profile_fields):
    fields = specific_profile_fields
    payload = {
        "username": os.getenv("TEST_EMAIL"),
        "password": os.getenv("TEST_PASSWORD"),
        "profile": True,
        "fields": fields,
    }

    response = client.post("/authenticate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] is True
    assert "timestamp" in data
    assert data["message"] == "Login successful."
    check_live_fields(data["profile"], fields)


@pytest.mark.secret_required
def test_integration_authenticate_with_all_profile_fields(client, check_live_profile):
    payload = {
        "username": os.getenv("TEST_EMAIL"),
        "password": os.getenv("TEST_PASSWORD"),
        "profile": True,
    }

    response = client.post("/authenticate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] is True
    assert "timestamp" in data
    assert data["message"] == "Login successful."
    check_live_profile(data["profile"])


@pytest.mark.secret_required
def test_integration_authenticate_invalid_password(client):
    payload = {
        "username": os.getenv("TEST_EMAIL"),
        "password": "wrongpass",
        "profile": True,
    }

    response = client.post("/authenticate", json=payload)
    assert response.status_code == 401
    data = response.json()
    assert data["status"] is False
    assert "Invalid username or password" in data["message"]


def test_integration_authenticate_missing_username(client):
    payload = {
        "password": "password",
        "profile": True,
    }

    response = client.post("/authenticate", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["status"] is False
    assert "Could not validate request data" in data["message"]
    assert "body.username: Field required" in data["message"]


def test_integration_authenticate_missing_password(client):
    payload = {
        "username": "username",
        "profile": True,
    }

    response = client.post("/authenticate", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["status"] is False
    assert "Could not validate request data" in data["message"]
    assert "body.password: Field required" in data["message"]


def test_integration_authenticate_username_wrong_type(client):
    payload = {
        "username": 12345,  # not a string
        "password": "password",
        "profile": True,
    }

    response = client.post("/authenticate", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["status"] is False
    assert "Could not validate request data" in data["message"]
    assert "body.username: Input should be a valid string" in data["message"]


def test_integration_authenticate_password_wrong_type(client):
    payload = {
        "username": "username",
        "password": 12345,
        "profile": True,
    }

    response = client.post("/authenticate", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["status"] is False
    assert "Could not validate request data" in data["message"]
    assert "body.password: Input should be a valid string" in data["message"]


def test_integration_authenticate_empty_password(client):
    payload = {
        "username": "username",
        "password": "",
        "profile": True,
    }

    response = client.post("/authenticate", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["status"] is False
    assert "body.password: Value error, Password cannot be empty." in data["message"]


def test_integration_authenticate_whitespace_only_password(client):
    payload = {
        "username": "username",
        "password": "   ",
        "profile": True,
    }

    response = client.post("/authenticate", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["status"] is False
    assert "body.password: Value error, Password cannot be empty." in data["message"]


def test_integration_authenticate_password_with_surrounding_whitespace(client):
    payload = {
        "username": "username",
        "password": "   password   ",
        "profile": True,
    }

    response = client.post("/authenticate", json=payload)
    assert response.status_code != 400
    data = response.json()
    assert data["status"] is False
    assert "Could not validate request data" not in data.get("message", "")


def test_integration_authenticate_profile_wrong_type(client):
    payload = {
        "username": "username",
        "password": "password",
        "profile": "true",
    }

    response = client.post("/authenticate", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["status"] is False
    assert "Could not validate request data" in data["message"]
    assert "body.profile: Input should be a valid boolean" in data["message"]


def test_integration_authenticate_fields_wrong_type(client):
    payload = {
        "username": "username",
        "password": "password",
        "profile": True,
        "fields": "prn,branch",
    }

    response = client.post("/authenticate", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["status"] is False
    assert "Could not validate request data" in data["message"]
    assert "body.fields: Input should be a valid list" in data["message"]


def test_integration_authenticate_fields_empty_list(client):
    payload = {
        "username": "username",
        "password": "password",
        "profile": True,
        "fields": [],
    }

    response = client.post("/authenticate", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["status"] is False
    assert "Could not validate request data" in data["message"]
    assert "body.fields: Value error, Fields must be a non-empty list or None." in data["message"]


def test_integration_authenticate_fields_invalid_field(client):
    payload = {
        "username": "username",
        "password": "password",
        "profile": True,
        "fields": ["invalid_field"],
    }

    response = client.post("/authenticate", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["status"] is False
    assert "Could not validate request data" in data["message"]
    assert "body.fields.0" in data["message"]


def test_integration_readme_redirect(client):
    redirect_url = "https://github.com/pesu-dev/auth"
    response = client.get("/readme", follow_redirects=False)
    assert response.status_code == 308
    assert response.reason_phrase == "Permanent Redirect"
    assert response.headers["location"] == redirect_url
    assert str(response.next_request.url) == redirect_url


def test_integration_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] is True
    assert data["message"] == "ok"


def test_integration_not_found(client):
    response = client.get("/nonexistent")
    assert response.status_code == 404
    data = response.json()
    assert data["status"] is False
    assert data["message"] == "No route matches this path."


def test_unhandled_exception_handler(client):
    response = client.get("/raiseUnhandled")
    assert response.status_code == 500
    data = response.json()
    assert data["status"] is False
    assert data["message"] == "Internal Server Error. Please try again later."


def test_integration_authenticate_deprecated_know_your_class_and_section_key_rejected(client):
    """Test that the old snake_case know_your_class_and_section key is rejected with 400."""
    payload = {
        "username": "username",
        "password": "password",
        "know_your_class_and_section": True,
    }

    response = client.post("/authenticate", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["status"] is False
    assert "Could not validate request data" in data["message"]
    assert "body.know_your_class_and_section: Extra inputs are not permitted" in data["message"]


def test_integration_authenticate_deprecated_know_your_class_and_section_camel_key_rejected(client):
    """Test that the deprecated knowYourClassAndSection key is rejected with 400."""
    payload = {
        "username": "username",
        "password": "password",
        "profile": True,
        "knowYourClassAndSection": True,
    }

    response = client.post("/authenticate", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["status"] is False
    assert "Could not validate request data" in data["message"]
    assert "body.knowYourClassAndSection: Extra inputs are not permitted" in data["message"]


def test_integration_authenticate_unknown_extra_key_rejected(client):
    """Test that any unknown key in the request body is rejected with 400."""
    payload = {
        "username": "username",
        "password": "password",
        "someUnknownField": "value",
    }

    response = client.post("/authenticate", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["status"] is False
    assert "Could not validate request data" in data["message"]
    assert "body.someUnknownField: Extra inputs are not permitted" in data["message"]


def test_integration_authenticate_deprecated_campus_code_in_fields_rejected(client):
    """Test that the old snake_case campus_code is rejected as a fields value."""
    payload = {
        "username": "username",
        "password": "password",
        "profile": True,
        "fields": ["campus_code"],
    }

    response = client.post("/authenticate", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["status"] is False
    assert "Could not validate request data" in data["message"]
    assert "body.fields.0" in data["message"]


def test_integration_authenticate_deprecated_institute_name_in_fields_rejected(client):
    """Test that the old snake_case institute_name is rejected as a fields value."""
    payload = {
        "username": "username",
        "password": "password",
        "profile": True,
        "fields": ["institute_name"],
    }

    response = client.post("/authenticate", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["status"] is False
    assert "Could not validate request data" in data["message"]
    assert "body.fields.0" in data["message"]


def test_integration_authenticate_removed_kycas_fields_rejected(client):
    """Test that the removed "Know Your Class and Section" field names are rejected with 400."""
    for field in ("cycle", "department", "instituteName"):
        payload = {
            "username": "username",
            "password": "password",
            "profile": True,
            "fields": [field],
        }

        response = client.post("/authenticate", json=payload)
        assert response.status_code == 400
        data = response.json()
        assert data["status"] is False
        assert "Could not validate request data" in data["message"]
        assert "body.fields.0" in data["message"]


@pytest.mark.parametrize(
    "field",
    ["first_name", "middle_name", "last_name", "branch_short_code", "date_of_birth", "campus_code"],
)
def test_integration_authenticate_snake_case_fields_rejected(client, field):
    """Fields are camelCase on the wire, like campusCode; the snake_case form is a 400."""
    payload = {"username": "username", "password": "password", "profile": True, "fields": [field]}

    response = client.post("/authenticate", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["status"] is False
    assert "Could not validate request data" in data["message"]
    assert "body.fields.0" in data["message"]


@pytest.mark.parametrize(
    "field", ["bloodGroup", "photo", "profilePicture", "programShortCode", "phone", "institute", "rollNumber"]
)
def test_integration_authenticate_fields_the_api_does_not_return_rejected(client, field):
    """PESU sends some of these and this API returned the others before 5.0.0; asking for any of them now is a 400."""
    payload = {"username": "username", "password": "password", "profile": True, "fields": [field]}

    response = client.post("/authenticate", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["status"] is False
    assert "body.fields.0" in data["message"]


def _validation_errors(client, field):
    for line in client.get("/metrics").text.splitlines():
        if line.startswith(f'pesu_auth_validation_errors_total{{field="{field}"}}'):
            return float(line.split()[-1])
    return 0.0


def test_integration_authenticate_exceeds_max_username_length(client, over_long_username):
    """Username exceeding max length returns 400 without leaking the value."""
    payload = {
        "username": over_long_username,
        "password": "testpassword",
    }

    before = _validation_errors(client, "username")
    response = client.post("/authenticate", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["status"] is False
    assert "username" in data["message"].lower()
    assert over_long_username not in data["message"]

    assert _validation_errors(client, "username") == before + 1


def test_integration_authenticate_exceeds_max_password_length(client, over_long_password):
    """Password exceeding max length returns 400 without leaking the value."""
    payload = {
        "username": "testuser",
        "password": over_long_password,
    }

    before = _validation_errors(client, "password")
    response = client.post("/authenticate", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["status"] is False
    assert "password" in data["message"].lower()
    assert over_long_password not in data["message"]

    assert _validation_errors(client, "password") == before + 1


def test_integration_authenticate_over_long_values_not_logged(client, caplog, over_long_username, over_long_password):
    """Over limit inputs are caught by validation and not written to logs."""
    payload = {
        "username": over_long_username,
        "password": over_long_password,
    }

    response = client.post("/authenticate", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["status"] is False
    assert "Request data could not be validated" in caplog.text
    assert over_long_password not in caplog.text
    assert over_long_username not in caplog.text


def assert_security_headers(response):
    """Verify standard security headers are present on a response."""
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["X-Frame-Options"] == "DENY"


def test_integration_security_headers_on_general_endpoints(client):
    """General endpoints must carry standard security headers and not carry Cache-Control: no-store."""
    for path in ["/", "/health", "/metrics"]:
        response = client.get(path)
        assert response.status_code == 200
        assert_security_headers(response)
        assert response.headers.get("Cache-Control") != "no-store"


def test_integration_authenticate_headers_on_validation_error(client):
    """The /authenticate endpoint must return security headers and Cache-Control: no-store on error."""
    response = client.post("/authenticate", json={})
    assert response.status_code == 400
    assert_security_headers(response)
    assert response.headers["Cache-Control"] == "no-store"


def test_integration_authenticate_success_headers(client, monkeypatch):
    """Test 200 OK has all security headers and no-store."""

    async def fake_success(*args, **kwargs):
        return {"status": True, "message": "Login successful."}

    monkeypatch.setattr("app.app.pesu_academy.authenticate", fake_success)

    response = client.post(
        "/authenticate",
        json={"username": "dummy_user", "password": "dummy_password"},
    )

    assert response.status_code == 200
    assert_security_headers(response)
    assert response.headers["Cache-Control"] == "no-store"


def test_integration_authenticate_401_headers(client, monkeypatch):
    """Test 401 Unauthorized has all security headers and no-store."""

    async def fake_unauthorized(*args, **kwargs):
        raise AuthenticationError("Invalid credentials")

    monkeypatch.setattr("app.app.pesu_academy.authenticate", fake_unauthorized)

    response = client.post(
        "/authenticate",
        json={"username": "dummy_user", "password": "wrong_password"},
    )

    assert response.status_code == 401
    assert_security_headers(response)
    assert response.headers["Cache-Control"] == "no-store"


def test_unhandled_exception_headers(client):
    """Unhandled exceptions on general endpoints return 500 with general security headers."""
    response = client.get("/raiseUnhandled")
    assert response.status_code == 500
    assert_security_headers(response)
    assert response.headers.get("Cache-Control") != "no-store"


def test_unhandled_exception_authenticate_headers(client, monkeypatch):
    """Unhandled exceptions on /authenticate return 500 with all security headers and no-store."""

    async def fake_crash(*args, **kwargs):
        raise RuntimeError("Unexpected failure")

    monkeypatch.setattr("app.app.pesu_academy.authenticate", fake_crash)

    response = client.post(
        "/authenticate",
        json={"username": "dummy_user", "password": "dummy_password"},
    )

    assert response.status_code == 500
    assert_security_headers(response)
    assert response.headers["Cache-Control"] == "no-store"


def test_integration_profile_key_omitted(client):
    """Profile key omitted but fields are still included."""
    payload = {"username": "username", "password": "password", "fields": ["name", "email", "srn", "prn"]}

    response = client.post("/authenticate", json=payload)
    data = response.json()
    assert response.status_code == 400
    assert "Fields can only be requested when profile is true" in data["message"]


def test_integration_profile_is_false(client):
    """Profile set to false."""
    payload = {"username": "username", "password": "password", "profile": False, "fields": ["name", "email", "srn"]}

    response = client.post("/authenticate", json=payload)
    data = response.json()
    assert response.status_code == 400
    assert "Fields can only be requested when profile is true" in data["message"]
