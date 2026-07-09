"""Unit tests for PESUAcademy.authenticate — current mobile-API implementation."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.exceptions.authentication import AuthenticationError
from app.pesu import PESUAcademy


@pytest.fixture
def pesu():
    return PESUAcademy()


def _make_client(login="SUCCESS", status_code=200, extra_data=None, token="tok", user_id="7"):
    """Build a mock httpx.AsyncClient context manager for the authenticate() call."""
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    data = {
        "login": login,
        "userId": int(user_id) if user_id else None,
        "loginId": "PES1201800001",
        "departmentId": "PES1UG19CS001",
        "className": "Sem-4",
        "batchClass": None,
        "program": "B.Tech.",
        "branch": "CSE",
        "sectionName": "B",
        "email": "test@example.com",
        "phone": "9876543210",
        "name": "Test User",
    }
    if extra_data:
        data.update(extra_data)

    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.json.return_value = data
    mock_response.headers = {"mobileappauthenticationtoken": token}
    mock_client.post.return_value = mock_response
    return mock_client


# ---------------------------------------------------------------------------
# Success paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_authenticate_success_no_profile(pesu):
    """Successful login with no profile requested returns only status and message."""
    with patch("app.pesu.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _make_client()
        result = await pesu.authenticate("user", "pass", profile=False)

    assert result["status"] is True
    assert result["message"] == "Login successful."
    assert "profile" not in result


@pytest.mark.asyncio
async def test_authenticate_success_with_profile(pesu):
    """Successful login with profile=True returns profile data."""
    with patch("app.pesu.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _make_client()
        with patch.object(pesu, "_fetch_name_as_in_sslc", new=AsyncMock(return_value=None)):
            result = await pesu.authenticate("user", "pass", profile=True, fields=["prn", "name"])

    assert result["status"] is True
    assert "profile" in result
    assert "prn" in result["profile"]
    assert "name" in result["profile"]
    # Field filtering works: branch was not requested
    assert "branch" not in result["profile"]


@pytest.mark.asyncio
async def test_authenticate_success_with_profile_all_fields(pesu):
    """When fields=None all profile fields are returned without filtering."""
    with patch("app.pesu.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _make_client()
        with patch.object(pesu, "_fetch_name_as_in_sslc", new=AsyncMock(return_value=None)):
            result = await pesu.authenticate("user", "pass", profile=True, fields=None)

    assert "profile" in result
    for key in ["name", "prn", "srn", "branch", "semester", "section", "email", "phone"]:
        assert key in result["profile"], f"'{key}' missing from profile"


# ---------------------------------------------------------------------------
# Failure paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_authenticate_connection_failure(pesu):
    """Network error during POST raises AuthenticationError."""
    with patch("app.pesu.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post.side_effect = Exception("timeout")
        mock_cls.return_value = mock_client

        with pytest.raises(AuthenticationError) as exc_info:
            await pesu.authenticate("user", "pass")
    assert "Connection failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_authenticate_non_200_status(pesu):
    """Non-200 HTTP status raises AuthenticationError."""
    with patch("app.pesu.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _make_client(status_code=503)

        with pytest.raises(AuthenticationError) as exc_info:
            await pesu.authenticate("user", "pass")
    assert "status code 503" in str(exc_info.value)


@pytest.mark.asyncio
async def test_authenticate_login_failure_with_error_message(pesu):
    """login != SUCCESS and errorMessage present → AuthenticationError with that message."""
    with patch("app.pesu.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _make_client(
            login="FAILURE",
            extra_data={"errorMessage": "Invalid username or password"},
        )

        with pytest.raises(AuthenticationError) as exc_info:
            await pesu.authenticate("user", "wrongpass")
    assert "Invalid username or password" in str(exc_info.value)


@pytest.mark.asyncio
async def test_authenticate_login_failure_no_error_message(pesu):
    """login != SUCCESS without errorMessage → fallback error message used."""
    with patch("app.pesu.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _make_client(login="FAILURE", extra_data={"errorMessage": None})

        with pytest.raises(AuthenticationError) as exc_info:
            await pesu.authenticate("baduser", "badpass")
    assert "baduser" in str(exc_info.value) or "Invalid username" in str(exc_info.value)


@pytest.mark.asyncio
async def test_authenticate_invalid_json_raises_error(pesu):
    """Unparseable JSON response raises AuthenticationError."""
    with patch("app.pesu.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = Exception("decode error")
        mock_client.post.return_value = mock_response
        mock_cls.return_value = mock_client

        with pytest.raises(AuthenticationError) as exc_info:
            await pesu.authenticate("user", "pass")
    assert "Invalid JSON response" in str(exc_info.value)
