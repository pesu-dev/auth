import os

import pytest
from fastapi.testclient import TestClient
from fastapi import APIRouter
from app.app import app

unhandled_router = APIRouter()


@unhandled_router.get("/raiseUnhandled")
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
def test_integration_authenticate_success_username_phone(client):
    payload = {
        "username": os.getenv("TEST_PHONE"),
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
def test_integration_authenticate_with_specific_profile_fields(client):
    email = os.getenv("TEST_EMAIL")
    password = os.getenv("TEST_PASSWORD")
    prn = os.getenv("TEST_PRN")
    branch = os.getenv("TEST_BRANCH")
    campus = os.getenv("TEST_CAMPUS")
    name = os.getenv("TEST_NAME")
    assert email is not None, "TEST_EMAIL environment variable not set"
    assert password is not None, "TEST_PASSWORD environment variable not set"
    assert prn is not None, "TEST_PRN environment variable not set"
    assert branch is not None, "TEST_BRANCH environment variable not set"
    assert campus is not None, "TEST_CAMPUS environment variable not set"
    assert name is not None, "TEST_NAME environment variable not set"

    expected_fields = ["prn", "branch", "campus", "name"]
    payload = {
        "username": email,
        "password": password,
        "profile": True,
        "fields": expected_fields,
    }

    response = client.post("/authenticate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] is True
    assert "timestamp" in data
    assert data["message"] == "Login successful."
    assert "profile" in data
    profile = data["profile"]
    assert len(profile) == len(expected_fields), (
        f"Expected {len(expected_fields)} fields in profile, got {len(profile)}"
    )

    assert profile["prn"] == prn
    assert profile["branch"] == branch
    assert profile["campus"] == campus
    assert profile["name"] == name
    assert "email" not in profile


@pytest.mark.secret_required
def test_integration_authenticate_with_all_profile_fields(client):
    name = os.getenv("TEST_NAME")
    email = os.getenv("TEST_EMAIL")
    password = os.getenv("TEST_PASSWORD")
    prn = os.getenv("TEST_PRN")
    srn = os.getenv("TEST_SRN")
    program = os.getenv("TEST_PROGRAM")
    semester = os.getenv("TEST_SEMESTER")
    section = os.getenv("TEST_SECTION")
    phone = os.getenv("TEST_PHONE")
    campus_code = int(os.getenv("TEST_CAMPUS_CODE"))
    branch = os.getenv("TEST_BRANCH")
    campus = os.getenv("TEST_CAMPUS")

    assert name is not None, "TEST_NAME environment variable not set"
    assert email is not None, "TEST_EMAIL environment variable not set"
    assert password is not None, "TEST_PASSWORD environment variable not set"
    assert prn is not None, "TEST_PRN environment variable not set"
    assert branch is not None, "TEST_BRANCH environment variable not set"
    assert campus is not None, "TEST_CAMPUS environment variable not set"
    assert srn is not None, "TEST_SRN environment variable not set"
    assert program is not None, "TEST_PROGRAM environment variable not set"
    assert semester is not None, "TEST_SEMESTER environment variable not set"
    assert section is not None, "TEST_SECTION environment variable not set"
    assert email is not None, "TEST_EMAIL environment variable not set"
    assert phone is not None, "TEST_PHONE environment variable not set"
    assert campus_code is not None, "TEST_CAMPUS_CODE environment variable not set"

    all_fields = [
        "name",
        "prn",
        "srn",
        "program",
        "branch",
        "semester",
        "section",
        "email",
        "phone",
        "campus_code",
        "campus",
    ]

    payload = {
        "username": email,
        "password": password,
        "profile": True,
    }

    response = client.post("/authenticate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] is True
    assert "timestamp" in data
    assert data["message"] == "Login successful."
    assert "profile" in data
    profile = data["profile"]
    assert len(profile) == len(all_fields), (
        f"Expected {len(all_fields)} fields in profile, got {len(profile)}"
    )

    assert profile["name"] == name
    assert profile["prn"] == prn
    assert profile["srn"] == srn
    assert profile["program"] == program
    assert profile["branch"] == branch
    assert profile["semester"] == semester
    assert profile["section"] == section
    assert profile["email"] == email
    assert profile["phone"] == phone
    assert profile["campus_code"] == campus_code
    assert profile["campus"] == campus


@pytest.mark.secret_required
def test_integration_authenticate_invalid_password(client):
    payload = {
        "username": os.getenv("TEST_EMAIL"),
        "password": "wrongpass",
        "profile": True,
    }

    response = client.post("/authenticate", json=payload)
    assert response.status_code in (200, 401, 500)
    data = response.json()
    assert data["status"] is False
    assert "Invalid" in data["message"] or "error" in data["message"].lower()


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


def test_integration_readme(client):
    response = client.get("/readme", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "https://github.com/pesu-dev/auth"


def test_integration_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_integration_not_found(client):
    response = client.get("/nonexistent")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == "Not Found"


def test_unhandled_exception_handler(client):
    response = client.get("/raiseUnhandled")
    assert response.status_code == 500
    data = response.json()
    assert data["status"] is False
    assert data["message"] == "Internal Server Error. Please try again later."
