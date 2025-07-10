import os

import pytest
from fastapi.testclient import TestClient

from app.app import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as client:
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
    branch_short_code = os.getenv("TEST_BRANCH_SHORT_CODE")
    campus = os.getenv("TEST_CAMPUS")
    assert email is not None, "TEST_EMAIL environment variable not set"
    assert password is not None, "TEST_PASSWORD environment variable not set"
    assert prn is not None, "TEST_PRN environment variable not set"
    assert branch is not None, "TEST_BRANCH environment variable not set"
    assert branch_short_code is not None, (
        "TEST_BRANCH_SHORT_CODE environment variable not set"
    )
    assert campus is not None, "TEST_CAMPUS environment variable not set"

    expected_fields = ["prn", "branch", "branch_short_code", "campus"]
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
    assert profile["branch_short_code"] == branch_short_code
    assert profile["campus"] == campus
    assert "name" not in profile


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
    campus_code_str = os.getenv("TEST_CAMPUS_CODE")
    branch = os.getenv("TEST_BRANCH")
    branch_short_code = os.getenv("TEST_BRANCH_SHORT_CODE")
    campus = os.getenv("TEST_CAMPUS")

    assert name is not None, "TEST_NAME environment variable not set"
    assert email is not None, "TEST_EMAIL environment variable not set"
    assert password is not None, "TEST_PASSWORD environment variable not set"
    assert prn is not None, "TEST_PRN environment variable not set"
    assert branch is not None, "TEST_BRANCH environment variable not set"
    assert branch_short_code is not None, (
        "TEST_BRANCH_SHORT_CODE environment variable not set"
    )
    assert campus is not None, "TEST_CAMPUS environment variable not set"
    assert srn is not None, "TEST_SRN environment variable not set"
    assert program is not None, "TEST_PROGRAM environment variable not set"
    assert semester is not None, "TEST_SEMESTER environment variable not set"
    assert section is not None, "TEST_SECTION environment variable not set"
    assert email is not None, "TEST_EMAIL environment variable not set"
    assert phone is not None, "TEST_PHONE environment variable not set"
    assert campus_code_str is not None, "TEST_CAMPUS_CODE environment variable not set"

    campus_code = int(campus_code_str)

    all_fields = [
        "name",
        "prn",
        "srn",
        "program",
        "branch_short_code",
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
    assert profile["branch_short_code"] == branch_short_code
    assert profile["branch"] == branch
    assert profile["semester"] == semester
    assert profile["section"] == section
    assert profile["email"] == email
    assert profile["phone"] == phone
    assert profile["campus_code"] == campus_code
    assert profile["campus"] == campus


@pytest.mark.secret_required
def test_integration_invalid_password(client):
    payload = {
        "username": os.getenv("TEST_EMAIL"),
        "password": "wrongpass",
        "profile": True,
    }

    response = client.post("/authenticate", json=payload)
    assert response.status_code in (200, 500)
    data = response.json()
    assert data["status"] is False
    assert "Invalid" in data["message"] or "error" in data["message"].lower()


def test_integration_missing_username(client):
    payload = {
        "password": "password",
        "profile": True,
    }

    response = client.post("/authenticate", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["status"] is False
    assert data["message"] == "Could not validate request data."
    assert data["details"] == "body.username: Field required"


def test_integration_missing_password(client):
    payload = {
        "username": "username",
        "profile": True,
    }

    response = client.post("/authenticate", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["status"] is False
    assert data["message"] == "Could not validate request data."
    assert data["details"] == "body.password: Field required"


def test_integration_username_wrong_type(client):
    payload = {
        "username": 12345,  # not a string
        "password": "password",
        "profile": True,
    }

    response = client.post("/authenticate", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["status"] is False
    assert data["message"] == "Could not validate request data."
    assert data["details"] == "body.username: Input should be a valid string"


def test_integration_password_wrong_type(client):
    payload = {
        "username": "username",
        "password": 12345,
        "profile": True,
    }

    response = client.post("/authenticate", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["status"] is False
    assert data["message"] == "Could not validate request data."
    assert data["details"] == "body.password: Input should be a valid string"


def test_integration_profile_wrong_type(client):
    payload = {
        "username": "username",
        "password": "password",
        "profile": "true",
    }

    response = client.post("/authenticate", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["status"] is False
    assert data["message"] == "Could not validate request data."
    assert data["details"] == "body.profile: Input should be a valid boolean"


def test_integration_fields_wrong_type(client):
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
    assert data["message"] == "Could not validate request data."
    assert data["details"] == "body.fields: Input should be a valid list"


def test_integration_fields_empty_list(client):
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
    assert data["message"] == "Could not validate request data."
    assert (
        data["details"]
        == "body.fields: Value error, Fields must be a non-empty list or None."
    )


def test_integration_fields_invalid_field(client):
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
    assert data["message"] == "Could not validate request data."
    assert data["details"].startswith("body.fields.0")


def test_integration_readme_route(client):
    response = client.get("/readme")
    assert response.status_code == 200
    assert "html" in response.headers["content-type"]
