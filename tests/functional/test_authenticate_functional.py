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
async def test_authenticate_success_username_srn(pesu_academy: PESUAcademy):
    srn = os.getenv("TEST_SRN")
    password = os.getenv("TEST_PASSWORD")
    assert srn is not None, "TEST_SRN environment variable not set"
    assert password is not None, "TEST_PASSWORD environment variable not set"

    result = await pesu_academy.authenticate(srn, password, profile=False, fields=None)
    assert result["status"] is True
    assert "profile" not in result


@pytest.mark.secret_required
@pytest.mark.asyncio
async def test_authenticate_with_specific_profile_fields(
    pesu_academy: PESUAcademy, check_live_fields, specific_profile_fields
):
    fields = specific_profile_fields
    result = await pesu_academy.authenticate(
        os.getenv("TEST_EMAIL"), os.getenv("TEST_PASSWORD"), profile=True, fields=fields
    )

    assert result["status"] is True
    assert "Login successful" in result["message"]
    check_live_fields(result["profile"], fields)


@pytest.mark.secret_required
@pytest.mark.asyncio
async def test_authenticate_with_all_profile_fields(pesu_academy: PESUAcademy, check_live_profile):
    result = await pesu_academy.authenticate(
        os.getenv("TEST_EMAIL"), os.getenv("TEST_PASSWORD"), profile=True, fields=None
    )

    assert result["status"] is True
    assert "Login successful" in result["message"]
    check_live_profile(result["profile"])


@pytest.mark.asyncio
async def test_authenticate_invalid_credentials(pesu_academy: PESUAcademy):
    with pytest.raises(AuthenticationError) as exc_info:
        await pesu_academy.authenticate("INVALID_USER", "wrongpass", profile=True, fields=None)

    assert exc_info.value.status_code == 401
    assert "Invalid username or password" in exc_info.value.message
