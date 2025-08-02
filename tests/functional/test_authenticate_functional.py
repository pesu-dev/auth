import os

import pytest

from app.exceptions.authentication import AuthenticationError
from app.pesu import PESUAcademy


@pytest.fixture
def pesu_academy():
    return PESUAcademy()


@pytest.mark.secret_required
@pytest.mark.asyncio
async def test_authenticate_success_username_email(pesu_academy: PESUAcademy):
    email = os.getenv("TEST_EMAIL")
    password = os.getenv("TEST_PASSWORD")
    assert email is not None, "TEST_EMAIL environment variable not set"
    assert password is not None, "TEST_PASSWORD environment variable not set"

    result = await pesu_academy.authenticate(email, password, profile=False, fields=None)
    assert result["status"] is True
    assert "Login successful" in result["message"]
    assert "profile" not in result


@pytest.mark.secret_required
@pytest.mark.asyncio
async def test_authenticate_success_username_prn(pesu_academy: PESUAcademy):
    prn = os.getenv("TEST_PRN")
    password = os.getenv("TEST_PASSWORD")
    assert prn is not None, "TEST_PRN environment variable not set"
    assert password is not None, "TEST_PASSWORD environment variable not set"

    result = await pesu_academy.authenticate(prn, password, profile=False, fields=None)
    assert result["status"] is True
    assert "Login successful" in result["message"]
    assert "profile" not in result


@pytest.mark.secret_required
@pytest.mark.asyncio
async def test_authenticate_success_username_phone(pesu_academy: PESUAcademy):
    phone = os.getenv("TEST_PHONE")
    password = os.getenv("TEST_PASSWORD")
    assert phone is not None, "TEST_PHONE environment variable not set"
    assert password is not None, "TEST_PASSWORD environment variable not set"

    result = await pesu_academy.authenticate(phone, password, profile=False, fields=None)
    assert result["status"] is True
    assert "Login successful" in result["message"]
    assert "profile" not in result


@pytest.mark.secret_required
@pytest.mark.asyncio
async def test_authenticate_with_specific_profile_fields(pesu_academy: PESUAcademy):
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

    fields = ["prn", "branch", "campus"]
    result = await pesu_academy.authenticate(email, password, profile=True, fields=fields)

    assert result["status"] is True
    assert "profile" in result
    assert "Login successful" in result["message"]
    profile = result["profile"]

    for field in fields:
        assert field in profile

    assert profile["prn"] == prn
    assert profile["branch"] == branch
    assert profile["campus"] == campus
    assert "name" not in profile
    assert "email" not in profile


@pytest.mark.secret_required
@pytest.mark.asyncio
async def test_authenticate_with_all_profile_fields(pesu_academy: PESUAcademy):
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

    result = await pesu_academy.authenticate(email, password, profile=True, fields=None)

    assert result["status"] is True
    assert "profile" in result
    assert "Login successful" in result["message"]
    profile = result["profile"]

    for field in all_fields:
        assert field in profile, f"Field '{field}' missing in profile"

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


@pytest.mark.asyncio
async def test_authenticate_invalid_credentials(pesu_academy: PESUAcademy):
    with pytest.raises(AuthenticationError):
        result = await pesu_academy.authenticate(
            "INVALID_USER",
            "wrongpass",
            profile=True,
            fields=None,
        )
        assert result["status"] is False
        assert "Invalid username or password" in result["message"]
        assert "profile" not in result
