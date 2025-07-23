import pytest
from unittest.mock import patch, AsyncMock, MagicMock

import app.pesu
from app.pesu import PESUAcademy
from app.exceptions.authentication import (
    ProfileFetchError,
    CSRFTokenError,
    AuthenticationError,
    ProfileParseError,
)


@pytest.fixture
def pesu():
    return PESUAcademy()


@patch("app.pesu.httpx.AsyncClient.get")
@pytest.mark.asyncio
async def test_get_profile_information_http_error(mock_get, pesu):
    mock_get.side_effect = Exception("HTTP request failed")
    with pytest.raises(ProfileFetchError):
        result = await pesu.get_profile_information(AsyncMock(), "testuser")
        assert "error" in result
        assert "Unable to fetch profile data" in result["error"]


@patch("app.pesu.httpx.AsyncClient.get")
@pytest.mark.asyncio
async def test_get_profile_information_non_200_status(mock_get, pesu):
    mock_response = AsyncMock()
    mock_response.status_code = 404
    mock_get.return_value = mock_response
    with pytest.raises(ProfileFetchError):
        result = await pesu.get_profile_information(AsyncMock(), "testuser")
        assert "error" in result
        assert "Unable to fetch profile data" in result["error"]


@patch("app.pesu.httpx.AsyncClient.get")
@pytest.mark.asyncio
async def test_authenticate_csrf_token_not_found(mock_get, pesu):
    mock_response = AsyncMock()
    mock_response.text = "<html><head></head><body>No CSRF token here</body></html>"
    mock_get.return_value = mock_response
    with pytest.raises(CSRFTokenError):
        result = await pesu.authenticate("testuser", "testpass")
        assert result["status"] is False
        assert "Unable to fetch csrf token" in result["message"]


@patch("app.pesu.httpx.AsyncClient.get")
@patch("app.pesu.httpx.AsyncClient.post")
@pytest.mark.asyncio
async def test_authenticate_post_request_failure(mock_post, mock_get, pesu):
    mock_get_response = AsyncMock()
    mock_get_response.text = '<meta name="csrf-token" content="fake-csrf-token">'
    mock_get.return_value = mock_get_response
    mock_post.side_effect = CSRFTokenError("POST request failed")
    with pytest.raises(CSRFTokenError):
        result = await pesu.authenticate("testuser", "testpass")
        assert result["status"] is False
        assert "Unable to authenticate" in result["message"]


@patch("app.pesu.httpx.AsyncClient.get")
@patch("app.pesu.httpx.AsyncClient.post")
@pytest.mark.asyncio
async def test_authenticate_csrf_token_missing_after_login(mock_post, mock_get, pesu):
    """Test authenticate when CSRF token is missing after successful login."""
    mock_get_response = AsyncMock()
    mock_get_response.text = '<meta name="csrf-token" content="fake-csrf-token">'
    mock_get.return_value = mock_get_response
    mock_post_response = AsyncMock()
    mock_post_response.text = "<html><body>Login successful but no CSRF token</body></html>"
    mock_post.return_value = mock_post_response
    with pytest.raises(CSRFTokenError):
        result = await pesu.authenticate("testuser", "testpass")
        assert result["status"] is True
        assert result["message"] == "Login successful."


@patch("app.pesu.httpx.AsyncClient.get")
@patch("app.pesu.httpx.AsyncClient.post")
@patch("app.pesu.PESUAcademy.get_profile_information")
@pytest.mark.asyncio
async def test_authenticate_with_profile_field_filtering(
    mock_get_profile, mock_post, mock_get, pesu
):
    mock_get_response = AsyncMock()
    mock_get_response.text = '<meta name="csrf-token" content="fake-csrf-token">'
    mock_get.return_value = mock_get_response
    mock_post_response = AsyncMock()
    mock_post_response.text = '<meta name="csrf-token" content="new-csrf-token">'
    mock_post.return_value = mock_post_response
    mock_get_profile.return_value = {
        "name": "Test User",
        "prn": "PES12345",
        "email": "test@example.com",
        "branch": "Computer Science",
        "campus": "RR",
    }
    result = await pesu.authenticate("testuser", "testpass", profile=True, fields=["name", "email"])
    assert result["status"] is True
    assert "profile" in result
    assert "name" in result["profile"]
    assert "email" in result["profile"]
    assert "prn" not in result["profile"]
    assert "branch" not in result["profile"]
    assert "campus" not in result["profile"]


@patch("app.pesu.httpx.AsyncClient.get")
@patch("app.pesu.httpx.AsyncClient.post")
@patch("app.pesu.PESUAcademy.get_profile_information")
@pytest.mark.asyncio
async def test_authenticate_with_profile_no_field_filtering(
    mock_get_profile, mock_post, mock_get, pesu
):
    mock_get_response = AsyncMock()
    mock_get_response.text = '<meta name="csrf-token" content="fake-csrf-token">'
    mock_get.return_value = mock_get_response
    mock_post_response = AsyncMock()
    mock_post_response.text = '<meta name="csrf-token" content="new-csrf-token">'
    mock_post.return_value = mock_post_response
    mock_get_profile.return_value = {
        k: "test_value" for k in app.pesu.PESUAcademyConstants.DEFAULT_FIELDS
    }
    result = await pesu.authenticate("testuser", "testpass", profile=True, fields=None)
    assert result["status"] is True
    for field in app.pesu.PESUAcademyConstants.DEFAULT_FIELDS:
        assert field in result["profile"]
        assert result["profile"][field] == "test_value"


@patch("app.pesu.HTMLParser")
@patch("app.pesu.httpx.AsyncClient.get")
@pytest.mark.asyncio
async def test_get_profile_information_profile_parse_error(mock_get, mock_html_parser, pesu):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<html></html>"
    mock_get.return_value = mock_response
    mock_soup = MagicMock()
    mock_soup.any_css_matches.return_value = True
    mock_soup.css.return_value = [MagicMock()] * 3
    mock_html_parser.return_value = mock_soup

    client = AsyncMock()
    client.get.return_value = mock_response

    with pytest.raises(ProfileParseError):
        await pesu.get_profile_information(client, "testuser")


@patch("app.pesu.HTMLParser")
@patch("app.pesu.httpx.AsyncClient.post")
@patch("app.pesu.httpx.AsyncClient.get")
@pytest.mark.asyncio
async def test_authenticate_login_form_present(mock_get, mock_post, mock_html_parser, pesu):
    mock_get_response = MagicMock()
    mock_get_response.text = '<meta name="csrf-token" content="fake-csrf-token">'
    mock_get_response.status_code = 200
    mock_get.return_value = mock_get_response
    mock_soup_csrf = MagicMock()
    mock_soup_csrf.css_first.side_effect = lambda selector: (
        MagicMock(attributes={"content": "fake-csrf-token"})
        if selector == "meta[name='csrf-token']"
        else None
    )
    mock_soup_login = MagicMock()
    mock_soup_login.css_first.side_effect = lambda selector: (
        MagicMock() if selector == "div.login-form" else None
    )
    mock_html_parser.side_effect = [mock_soup_csrf, mock_soup_login]
    mock_post_response = MagicMock()
    mock_post_response.text = "<html><body><div class='login-form'></div></body></html>"
    mock_post_response.status_code = 200
    mock_post.return_value = mock_post_response
    with pytest.raises(AuthenticationError):
        await pesu.authenticate("testuser", "testpass")


@patch("app.pesu.HTMLParser")
@patch("app.pesu.httpx.AsyncClient.post")
@patch("app.pesu.httpx.AsyncClient.get")
@pytest.mark.asyncio
async def test_authenticate_csrf_token_missing_after_login_strict(
    mock_get, mock_post, mock_html_parser, pesu
):
    mock_get_response = AsyncMock()
    mock_get_response.text = '<meta name="csrf-token" content="fake-csrf-token">'
    mock_get.return_value = mock_get_response
    mock_post_response = AsyncMock()
    mock_post_response.text = "<html><body>Login successful but no CSRF token</body></html>"
    mock_post.return_value = mock_post_response
    mock_soup = MagicMock()

    def css_first(selector):
        if selector == "div.login-form":
            return None
        if selector == "meta[name='csrf-token']":
            return None
        return None

    mock_soup.css_first.side_effect = css_first
    mock_html_parser.return_value = mock_soup
    with pytest.raises(CSRFTokenError):
        await pesu.authenticate("testuser", "testpass")
