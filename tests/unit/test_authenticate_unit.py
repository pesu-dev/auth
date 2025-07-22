from unittest.mock import AsyncMock, patch

import pytest

from app.pesu import PESUAcademy
from app.exceptions.authentication import CSRFTokenError, AuthenticationError


@pytest.fixture
def pesu():
    return PESUAcademy()


@patch("app.pesu.httpx.AsyncClient.get")
@patch("app.pesu.httpx.AsyncClient.post")
@pytest.mark.asyncio
async def test_authenticate_success_no_profile(mock_post, mock_get, pesu):
    # Mock GET home page response with csrf token meta
    mock_get_response = AsyncMock()
    mock_get_response.text = '<meta name="csrf-token" content="fake-csrf-token">'
    mock_get_response.status_code = 200
    mock_get.return_value = mock_get_response

    # Mock POST login success response with csrf token meta
    mock_post_response = AsyncMock()
    mock_post_response.text = '<meta name="csrf-token" content="new-csrf-token">'
    mock_post.return_value = mock_post_response

    result = await pesu.authenticate("user", "pass", profile=False)

    assert result["status"] is True
    assert result["message"] == "Login successful."
    assert "profile" not in result


@patch("app.pesu.httpx.AsyncClient.get")
@patch("app.pesu.httpx.AsyncClient.post")
@patch("app.pesu.PESUAcademy.get_profile_information")
@pytest.mark.asyncio
async def test_authenticate_success_with_profile(mock_get_profile, mock_post, mock_get, pesu):
    mock_get_response = AsyncMock()
    mock_get_response.text = '<meta name="csrf-token" content="fake-csrf-token">'
    mock_get.return_value = mock_get_response

    mock_post_response = AsyncMock()
    mock_post_response.text = '<meta name="csrf-token" content="new-csrf-token">'
    mock_post.return_value = mock_post_response

    mock_get_profile.return_value = {
        "prn": "PES12345",
        "name": "Test User",
        "branch": "Computer Science and Engineering",
    }

    result = await pesu.authenticate("user", "pass", profile=True, fields=["prn", "name"])

    assert result["status"] is True
    assert "profile" in result
    assert "prn" in result["profile"]
    assert "name" in result["profile"]
    # Field filtering works, branch is omitted since not requested
    assert "branch" not in result["profile"]


@patch("app.pesu.httpx.AsyncClient.get")
@pytest.mark.asyncio
async def test_authenticate_csrf_fetch_failure(mock_get, pesu):
    mock_get.side_effect = CSRFTokenError("CSRF fetch failed")

    with pytest.raises(CSRFTokenError):
        result = await pesu.authenticate("user", "pass")
        assert result["status"] is False
        assert "Unable to fetch csrf token" in result["message"]


@patch("app.pesu.httpx.AsyncClient.get")
@patch("app.pesu.httpx.AsyncClient.post")
@pytest.mark.asyncio
async def test_authenticate_login_failure(mock_post, mock_get, pesu):
    mock_get_response = AsyncMock()
    mock_get_response.text = '<meta name="csrf-token" content="fake-csrf-token">'
    mock_get.return_value = mock_get_response

    # Simulate login failure: login form div present
    mock_post_response = AsyncMock()
    mock_post_response.text = '<div class="login-form">Login error</div>'
    mock_post.return_value = mock_post_response

    with pytest.raises(AuthenticationError):
        result = await pesu.authenticate("user", "pass")

        assert result["status"] is False
        assert "Invalid username or password" in result["message"]
