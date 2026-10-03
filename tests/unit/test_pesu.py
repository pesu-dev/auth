import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.exceptions.authentication import (
    AuthenticationError,
    CSRFTokenError,
    ProfileFetchError,
    ProfileParseError,
)
from app.pesu import PESUAcademy


@pytest.fixture
def pesu():
    return PESUAcademy()


@patch("app.pesu.httpx2.AsyncClient.get")
@pytest.mark.asyncio
async def test_get_profile_information_http_error(mock_get, pesu):
    mock_get.side_effect = Exception("HTTP request failed")
    with pytest.raises(ProfileFetchError):
        result = await pesu.get_profile_information(AsyncMock(), "testuser")
        assert "error" in result
        assert "Unable to fetch profile data" in result["error"]


@patch("app.pesu.httpx2.AsyncClient.get")
@pytest.mark.asyncio
async def test_get_profile_information_non_200_status(mock_get, pesu):
    mock_response = AsyncMock()
    mock_response.status_code = 404
    mock_get.return_value = mock_response
    with pytest.raises(ProfileFetchError):
        result = await pesu.get_profile_information(AsyncMock(), "testuser")
        assert "error" in result
        assert "Unable to fetch profile data" in result["error"]


@patch("app.pesu.httpx2.AsyncClient.get")
@pytest.mark.asyncio
async def test_authenticate_csrf_token_not_found(mock_get, pesu):
    mock_response = AsyncMock()
    mock_response.text = "<html><head></head><body>No CSRF token here</body></html>"
    mock_get.return_value = mock_response
    with pytest.raises(CSRFTokenError):
        result = await pesu.authenticate("testuser", "testpass")
        assert result["status"] is False
        assert "Unable to fetch csrf token" in result["message"]


@patch("app.pesu.httpx2.AsyncClient.get")
@patch("app.pesu.httpx2.AsyncClient.post")
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


@patch("app.pesu.httpx2.AsyncClient.get")
@patch("app.pesu.httpx2.AsyncClient.post")
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


@patch("app.pesu.httpx2.AsyncClient.get")
@patch("app.pesu.httpx2.AsyncClient.post")
@patch("app.pesu.PESUAcademy.get_profile_information")
@pytest.mark.asyncio
async def test_authenticate_with_profile_field_filtering(
    mock_get_profile,
    mock_post,
    mock_get,
    pesu,
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


@patch("app.pesu.httpx2.AsyncClient.get")
@patch("app.pesu.httpx2.AsyncClient.post")
@patch("app.pesu.PESUAcademy.get_profile_information")
@pytest.mark.asyncio
async def test_authenticate_with_profile_no_field_filtering(
    mock_get_profile,
    mock_post,
    mock_get,
    pesu,
):
    mock_get_response = AsyncMock()
    mock_get_response.text = '<meta name="csrf-token" content="fake-csrf-token">'
    mock_get.return_value = mock_get_response
    mock_post_response = AsyncMock()
    mock_post_response.text = '<meta name="csrf-token" content="new-csrf-token">'
    mock_post.return_value = mock_post_response
    mock_get_profile.return_value = dict.fromkeys(PESUAcademy.DEFAULT_FIELDS, "test_value")
    result = await pesu.authenticate("testuser", "testpass", profile=True, fields=None)
    assert result["status"] is True
    for field in PESUAcademy.DEFAULT_FIELDS:
        assert field in result["profile"]
        assert result["profile"][field] == "test_value"


@patch("app.pesu.HTMLParser")
@patch("app.pesu.httpx2.AsyncClient.get")
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
@patch("app.pesu.httpx2.AsyncClient.post")
@patch("app.pesu.httpx2.AsyncClient.get")
@pytest.mark.asyncio
async def test_authenticate_login_form_present(mock_get, mock_post, mock_html_parser, pesu):
    mock_get_response = MagicMock()
    mock_get_response.text = '<meta name="csrf-token" content="fake-csrf-token">'
    mock_get_response.status_code = 200
    mock_get.return_value = mock_get_response
    mock_soup_csrf = MagicMock()
    mock_soup_csrf.css_first.side_effect = lambda selector: (
        MagicMock(attributes={"content": "fake-csrf-token"}) if selector == "meta[name='csrf-token']" else None
    )
    mock_soup_login = MagicMock()
    mock_soup_login.css_first.side_effect = lambda selector: MagicMock() if selector == "div.login-form" else None
    mock_html_parser.side_effect = [mock_soup_csrf, mock_soup_login]
    mock_post_response = MagicMock()
    mock_post_response.text = "<html><body><div class='login-form'></div></body></html>"
    mock_post_response.status_code = 200
    mock_post.return_value = mock_post_response
    with pytest.raises(AuthenticationError):
        await pesu.authenticate("testuser", "testpass")


@patch("app.pesu.HTMLParser")
@patch("app.pesu.httpx2.AsyncClient.post")
@patch("app.pesu.httpx2.AsyncClient.get")
@pytest.mark.asyncio
async def test_authenticate_csrf_token_missing_after_login_strict(
    mock_get,
    mock_post,
    mock_html_parser,
    pesu,
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
            return
        if selector == "meta[name='csrf-token']":
            return
        return

    mock_soup.css_first.side_effect = css_first
    mock_html_parser.return_value = mock_soup
    with pytest.raises(CSRFTokenError):
        await pesu.authenticate("testuser", "testpass")


@patch("app.pesu.HTMLParser")
@patch("app.pesu.httpx2.AsyncClient.get")
@pytest.mark.asyncio
async def test_get_profile_information_unknown_campus_code(
    mock_get,
    mock_html_parser,
    pesu,
    caplog,
):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<html></html>"
    mock_get.return_value = mock_response

    def make_div(key, value):
        div = MagicMock()
        key_label = MagicMock()
        key_label.text.return_value = key
        value_label = MagicMock()
        value_label.text.return_value = value

        def css_first(selector):
            if selector == "label.lbl-title-light":
                return key_label
            if selector == "label.lbl-title-light + label":
                return value_label
            return None

        div.css_first.side_effect = css_first
        return div

    form_group_elems = [
        make_div("Name", "Test User"),
        make_div("SRN", "PES1234567"),
        make_div("PESU Id", "PES3XXXXX"),
        make_div("Program", "BTech"),
        make_div("Branch", "Computer Science and Engineering"),
        make_div("Semester", "6"),
        make_div("Section", "A"),
    ]

    mock_soup = MagicMock()
    mock_container = MagicMock()
    mock_container.css.return_value = form_group_elems

    email_node = MagicMock()
    email_node.attributes = {"value": "test@example.com"}
    phone_node = MagicMock()
    phone_node.attributes = {"value": "1234567890"}

    def css_first(selector):
        if selector == "div.elem-info-wrapper":
            return mock_container
        if selector == "#updateMail":
            return email_node
        if selector == "#updateContact":
            return phone_node
        return None

    mock_soup.css_first.side_effect = css_first
    mock_html_parser.return_value = mock_soup

    client = AsyncMock()
    client.get.return_value = mock_response

    with caplog.at_level("INFO"):
        profile = await pesu.get_profile_information(client, "testuser")
        assert profile["prn"] == "PES3XXXXX"
        assert profile["name"] == "Test User"
        assert profile["branch"] == "Computer Science and Engineering"
        assert profile["email"] == "test@example.com"
        assert profile["phone"] == "1234567890"
        assert "campusCode" not in profile
        assert "campus" not in profile
        assert any(
            "Unknown campus code: 3 parsed from PRN=PES3XXXXX for user=testuser" in record.message
            for record in caplog.records
        )
        assert any(
            "Complete profile information retrieved for user=testuser" in record.message for record in caplog.records
        )


@patch("app.pesu.HTMLParser")
@patch("app.pesu.httpx2.AsyncClient.get")
@pytest.mark.asyncio
async def test_get_profile_information_campus_code_rr_ec(mock_get, mock_html_parser, pesu):
    """Test that PRNs with PES1 and PES2 set the correct campus and campusCode."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<html></html>"
    mock_get.return_value = mock_response

    def make_div(key, value):
        div = MagicMock()
        key_label = MagicMock()
        key_label.text.return_value = key
        value_label = MagicMock()
        value_label.text.return_value = value

        def css_first(selector):
            if selector == "label.lbl-title-light":
                return key_label
            if selector == "label.lbl-title-light + label":
                return value_label
            return None

        div.css_first.side_effect = css_first
        return div

    # Subcase 1: PES1... (RR campus)
    form_group_elems_rr = [
        make_div("Name", "Test User"),
        make_div("SRN", "PES1234567"),
        make_div("PESU Id", "PES1XXXXX"),
        make_div("Program", "BTech"),
        make_div("Branch", "Computer Science and Engineering"),
        make_div("Semester", "6"),
        make_div("Section", "A"),
    ]
    mock_soup_rr = MagicMock()
    mock_container_rr = MagicMock()
    mock_container_rr.css.return_value = form_group_elems_rr
    mock_soup_rr.css_first.side_effect = lambda selector: (
        mock_container_rr if selector == "div.elem-info-wrapper" else None
    )
    mock_html_parser.return_value = mock_soup_rr

    client = AsyncMock()
    client.get.return_value = mock_response

    profile_rr = await pesu.get_profile_information(client, "testuser")
    assert profile_rr["campusCode"] == 1
    assert profile_rr["campus"] == "RR"

    # Subcase 2: PES2... (EC campus)
    form_group_elems_ec = [
        make_div("Name", "Test User"),
        make_div("SRN", "PES2234567"),
        make_div("PESU Id", "PES2YYYYY"),
        make_div("Program", "BTech"),
        make_div("Branch", "Computer Science and Engineering"),
        make_div("Semester", "6"),
        make_div("Section", "A"),
    ]
    mock_soup_ec = MagicMock()
    mock_container_ec = MagicMock()
    mock_container_ec.css.return_value = form_group_elems_ec
    mock_soup_ec.css_first.side_effect = lambda selector: (
        mock_container_ec if selector == "div.elem-info-wrapper" else None
    )
    mock_html_parser.return_value = mock_soup_ec

    profile_ec = await pesu.get_profile_information(client, "testuser")
    assert profile_ec["campusCode"] == 2
    assert profile_ec["campus"] == "EC"


@patch("app.pesu.HTMLParser")
@patch("app.pesu.httpx2.AsyncClient.get")
@pytest.mark.asyncio
async def test_get_profile_information_no_profile_data(mock_get, mock_html_parser, pesu):
    """Test that ProfileParseError is raised when no profile data is parsed (parsing loop runs but nothing added)."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<html></html>"
    mock_get.return_value = mock_response
    mock_soup = MagicMock()
    mock_soup.any_css_matches.return_value = True
    mock_soup.css.return_value = [MagicMock(text=MagicMock(return_value="foo bar")) for _ in range(7)]
    mock_soup.css_first.return_value = None
    mock_html_parser.return_value = mock_soup

    client = AsyncMock()
    client.get.return_value = mock_response
    with pytest.raises(ProfileParseError) as exc_info:
        await pesu.get_profile_information(client, "testuser")
    assert "Failed to parse student profile page from PESU Academy for user=testuser." in str(exc_info.value)
    assert "The webpage might have changed." in str(exc_info.value)


@patch("app.pesu.HTMLParser")
@patch("app.pesu.httpx2.AsyncClient.get")
@patch("app.pesu.PESUAcademy._extract_and_update_profile", new_callable=MagicMock)
@pytest.mark.asyncio
async def test_get_profile_information_empty_profile_triggers_final_parse_error(
    mock_extract,
    mock_get,
    mock_html_parser,
    pesu,
):
    mock_extract.return_value = None

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<html></html>"
    mock_get.return_value = mock_response

    mock_container = MagicMock()
    mock_container.css.return_value = [MagicMock() for _ in range(7)]
    mock_soup = MagicMock()
    mock_soup.css_first.side_effect = lambda selector: mock_container if selector == "div.elem-info-wrapper" else None
    mock_html_parser.return_value = mock_soup

    client = AsyncMock()
    client.get.return_value = mock_response

    with pytest.raises(ProfileParseError) as exc_info:
        await pesu.get_profile_information(client, "testuser")
    assert "No profile data could be extracted for user=testuser" in str(exc_info.value)


@pytest.mark.asyncio
async def test_extract_and_update_profile_key_label_missing(pesu):
    node = MagicMock()
    node.css_first.return_value = None  # key label missing
    profile = {}
    with pytest.raises(ProfileParseError) as exc_info:
        await pesu._extract_and_update_profile(node, 0, profile)
    assert "Could not parse key for field at index 0" in str(exc_info.value)


@pytest.mark.asyncio
async def test_extract_and_update_profile_value_label_missing(pesu):
    node = MagicMock()
    key_label = MagicMock()
    key_label.text.return_value = "Name"

    def css_first(selector):
        if selector == "label.lbl-title-light":
            return key_label
        if selector == "label.lbl-title-light + label":
            return None  # value label missing
        return None

    node.css_first.side_effect = css_first
    profile = {}
    with pytest.raises(ProfileParseError) as exc_info:
        await pesu._extract_and_update_profile(node, 0, profile)
    assert "Could not parse value for field at index 0" in str(exc_info.value)


@pytest.mark.asyncio
async def test_extract_and_update_profile_unknown_key(pesu):
    node = MagicMock()
    key_label = MagicMock()
    key_label.text.return_value = "UnknownKey"
    value_label = MagicMock()
    value_label.text.return_value = "SomeValue"

    def css_first(selector):
        if selector == "label.lbl-title-light":
            return key_label
        if selector == "label.lbl-title-light + label":
            return value_label
        return None

    node.css_first.side_effect = css_first
    profile = {}
    with pytest.raises(ProfileParseError) as exc_info:
        await pesu._extract_and_update_profile(node, 0, profile)
    assert "Unknown key: 'UnknownKey' in the profile page" in str(exc_info.value)


def test_default_fields_is_list():
    assert isinstance(PESUAcademy.DEFAULT_FIELDS, list)
    assert "prn" in PESUAcademy.DEFAULT_FIELDS
    assert "name" in PESUAcademy.DEFAULT_FIELDS
    assert "srn" in PESUAcademy.DEFAULT_FIELDS
    assert "program" in PESUAcademy.DEFAULT_FIELDS
    assert "branch" in PESUAcademy.DEFAULT_FIELDS
    assert "semester" in PESUAcademy.DEFAULT_FIELDS
    assert "section" in PESUAcademy.DEFAULT_FIELDS
    assert "email" in PESUAcademy.DEFAULT_FIELDS
    assert "phone" in PESUAcademy.DEFAULT_FIELDS
    assert "campusCode" in PESUAcademy.DEFAULT_FIELDS
    assert "campus" in PESUAcademy.DEFAULT_FIELDS


@pytest.mark.asyncio
@patch("app.pesu.PESUAcademy._fetch_new_client_with_csrf_token")
async def test_prefetch_client_closes_old_client_on_second_call(mock_fetch, pesu):
    old_client = AsyncMock()
    new_client = AsyncMock()
    mock_fetch.side_effect = [
        (old_client, "token-1"),
        (new_client, "token-2"),
    ]

    await pesu.prefetch_client_with_csrf_token()
    await pesu.prefetch_client_with_csrf_token()

    old_client.aclose.assert_awaited_once()


@pytest.mark.asyncio
@patch("app.pesu.PESUAcademy._get_client_with_csrf_token")
async def test_authenticate_closes_client_on_authentication_error(mock_get_client, pesu):
    """The request's client must be closed when the credentials are rejected."""
    client = AsyncMock()
    login_failed_response = AsyncMock()
    login_failed_response.text = '<div class="login-form"></div>'
    client.post.return_value = login_failed_response
    mock_get_client.return_value = (client, "fake-csrf-token")

    with pytest.raises(AuthenticationError):
        await pesu.authenticate("testuser", "wrongpass")

    client.aclose.assert_awaited_once()


@pytest.mark.asyncio
@patch("app.pesu.PESUAcademy._get_client_with_csrf_token")
async def test_authenticate_closes_client_on_missing_post_login_csrf_token(mock_get_client, pesu):
    """The request's client must be closed when the post-login CSRF token is absent."""
    client = AsyncMock()
    response = AsyncMock()
    response.text = "<html><body>no csrf meta tag and no login form</body></html>"
    client.post.return_value = response
    mock_get_client.return_value = (client, "fake-csrf-token")

    with pytest.raises(CSRFTokenError):
        await pesu.authenticate("testuser", "testpass")

    client.aclose.assert_awaited_once()


@pytest.mark.asyncio
@patch("app.pesu.PESUAcademy.get_profile_information")
@patch("app.pesu.PESUAcademy._get_client_with_csrf_token")
async def test_authenticate_closes_client_on_profile_fetch_error(mock_get_client, mock_get_profile, pesu):
    """The request's client must be closed when profile fetching fails."""
    client = AsyncMock()
    response = AsyncMock()
    response.text = '<meta name="csrf-token" content="new-csrf-token">'
    client.post.return_value = response
    mock_get_client.return_value = (client, "fake-csrf-token")
    mock_get_profile.side_effect = ProfileFetchError("boom")

    with pytest.raises(ProfileFetchError):
        await pesu.authenticate("testuser", "testpass", profile=True)

    client.aclose.assert_awaited_once()


@pytest.mark.asyncio
@patch("app.pesu.PESUAcademy._get_client_with_csrf_token")
async def test_authenticate_closes_client_on_success(mock_get_client, pesu):
    """The request's client must also be closed on the success path."""
    client = AsyncMock()
    response = AsyncMock()
    response.text = '<meta name="csrf-token" content="new-csrf-token">'
    client.post.return_value = response
    mock_get_client.return_value = (client, "fake-csrf-token")

    result = await pesu.authenticate("testuser", "testpass")

    assert result["status"] is True
    client.aclose.assert_awaited_once()


@pytest.mark.asyncio
@patch("app.pesu.httpx2.AsyncClient")
async def test_fetch_new_client_closes_client_when_csrf_token_missing(mock_client_class, pesu):
    """A client that never gets returned to the caller must not be leaked."""
    client = AsyncMock()
    response = AsyncMock()
    response.text = "<html><body>no csrf meta tag</body></html>"
    client.get.return_value = response
    mock_client_class.return_value = client

    with pytest.raises(CSRFTokenError):
        await pesu._fetch_new_client_with_csrf_token()

    client.aclose.assert_awaited_once()


@pytest.mark.asyncio
@patch("app.pesu.httpx2.AsyncClient")
async def test_fetch_new_client_closes_client_when_get_fails(mock_client_class, pesu):
    """A client whose initial GET fails must not be leaked."""
    client = AsyncMock()
    client.get.side_effect = RuntimeError("connection reset")
    mock_client_class.return_value = client

    with pytest.raises(RuntimeError):
        await pesu._fetch_new_client_with_csrf_token()

    client.aclose.assert_awaited_once()


@pytest.mark.asyncio
@patch("app.pesu.PESUAcademy._fetch_new_client_with_csrf_token")
async def test_prefetch_survives_a_broken_old_client(mock_fetch, pesu, caplog):
    """A cached client that refuses to close must not stop the refresh; the failure is logged."""
    old_client = AsyncMock()
    old_client.aclose.side_effect = RuntimeError("old client refused to close")
    new_client = AsyncMock()
    pesu._client = old_client
    pesu._csrf_token = "stale-token"
    mock_fetch.return_value = (new_client, "fresh-token")

    await pesu.prefetch_client_with_csrf_token()

    assert "Failed to close an HTTP client cleanly." in caplog.text
    # The refresh still went through, and the new client was cached rather than closed
    assert pesu._client is new_client
    assert pesu._csrf_token == "fresh-token"
    new_client.aclose.assert_not_awaited()


@pytest.mark.asyncio
@patch("app.pesu.PESUAcademy._fetch_new_client_with_csrf_token")
async def test_prefetch_closes_new_client_when_cancelled_before_caching(mock_fetch, pesu):
    """A prefetch cancelled before it can cache its client must close it, not leak it."""
    new_client = AsyncMock()
    mock_fetch.return_value = (new_client, "fresh-token")

    # Hold the lock so the prefetch blocks at the swap, exactly as it would during shutdown
    await pesu._csrf_lock.acquire()
    task = asyncio.create_task(pesu._prefetch_client_with_csrf_token())
    await asyncio.sleep(0.01)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    pesu._csrf_lock.release()

    new_client.aclose.assert_awaited_once()
    assert pesu._client is None


@pytest.mark.asyncio
@patch("app.pesu.PESUAcademy._fetch_new_client_with_csrf_token")
async def test_close_client_cancels_in_flight_prefetch(mock_fetch, pesu):
    """Shutdown must stop in-flight prefetches, or one can cache a client after the close."""
    slow_client = AsyncMock()

    async def slow_fetch():
        await asyncio.sleep(3600)
        return slow_client, "never-arrives"

    mock_fetch.side_effect = slow_fetch
    pesu._spawn_prefetch_task()
    await asyncio.sleep(0.01)
    assert len(pesu._prefetch_tasks) == 1
    task = next(iter(pesu._prefetch_tasks))

    await pesu.close_client()

    assert task.cancelled()
    assert pesu._client is None
    assert pesu._csrf_token is None


@pytest.mark.asyncio
async def test_close_client_clears_cached_client_and_token(pesu):
    """The cached client is closed and both cache slots are cleared."""
    client = AsyncMock()
    pesu._client = client
    pesu._csrf_token = "cached-token"

    await pesu.close_client()

    client.aclose.assert_awaited_once()
    assert pesu._client is None
    assert pesu._csrf_token is None


@pytest.mark.asyncio
@patch("app.pesu.PESUAcademy._fetch_new_client_with_csrf_token")
async def test_get_client_holds_strong_reference_to_prefetch_task(mock_fetch, pesu):
    """The background prefetch task must be referenced so it cannot be garbage collected."""
    mock_fetch.side_effect = [(AsyncMock(), "token-1"), (AsyncMock(), "token-2")]

    await pesu._get_client_with_csrf_token()

    assert len(pesu._prefetch_tasks) == 1
    task = next(iter(pesu._prefetch_tasks))

    await task
    # add_done_callback fires via loop.call_soon, so yield once to let it run
    await asyncio.sleep(0)

    assert pesu._prefetch_tasks == set()


@pytest.mark.asyncio
@patch("app.pesu.PESUAcademy._fetch_new_client_with_csrf_token")
async def test_prefetch_task_failure_is_logged(mock_fetch, pesu, caplog):
    """A failing background prefetch must be logged, not silently swallowed."""
    mock_fetch.side_effect = [(AsyncMock(), "token-1"), RuntimeError("upstream is down")]

    await pesu._get_client_with_csrf_token()
    task = next(iter(pesu._prefetch_tasks))
    await asyncio.gather(task, return_exceptions=True)
    await asyncio.sleep(0)

    assert "Background CSRF token prefetch failed" in caplog.text
    assert "upstream is down" in caplog.text


@pytest.mark.asyncio
async def test_prefetch_task_cancellation_is_not_logged(pesu, caplog):
    """A cancelled prefetch task is expected during shutdown and must not be logged as a failure."""
    task = asyncio.create_task(asyncio.sleep(3600))
    pesu._prefetch_tasks.add(task)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)

    pesu._on_prefetch_task_done(task)

    assert pesu._prefetch_tasks == set()
    assert "Background CSRF token prefetch failed" not in caplog.text


@pytest.mark.asyncio
@patch("app.pesu.PESUAcademy._fetch_new_client_with_csrf_token")
async def test_authenticate_triggers_exactly_one_prefetch(mock_fetch, pesu):
    """One authentication must cause one inline fetch plus exactly one background prefetch."""
    client = AsyncMock()
    response = MagicMock()
    response.text = '<meta name="csrf-token" content="new-csrf-token">'
    client.post.return_value = response
    mock_fetch.side_effect = [(client, "token-1"), (AsyncMock(), "token-2")]

    await pesu.authenticate("testuser", "testpass")

    for task in list(pesu._prefetch_tasks):
        await asyncio.gather(task, return_exceptions=True)
    await asyncio.sleep(0)

    # One cold-cache inline fetch for this request, one prefetch for the next. Never more.
    assert mock_fetch.await_count == 2


@pytest.mark.asyncio
@patch("app.pesu.PESUAcademy._fetch_new_client_with_csrf_token")
async def test_prefetch_closes_new_client_when_cancelled_during_cleanup(mock_fetch, pesu):
    """A second cancellation, landing while the client is being closed, must not abandon it.

    The cleanup in `_prefetch_client_with_csrf_token` runs from an `except BaseException` handler,
    so it is already unwinding from one cancellation when a shutdown can cancel it again. Without
    shielding, that second cancellation stops `aclose()` part-way and leaks the connection pool.
    """
    close_started = asyncio.Event()
    close_finished = asyncio.Event()

    async def slow_aclose():
        close_started.set()
        await asyncio.sleep(0.05)
        close_finished.set()

    new_client = AsyncMock()
    new_client.aclose.side_effect = slow_aclose
    mock_fetch.return_value = (new_client, "fresh-token")

    # Hold the lock so the prefetch blocks at the swap, exactly as it would during shutdown
    await pesu._csrf_lock.acquire()
    task = asyncio.create_task(pesu._prefetch_client_with_csrf_token())
    await asyncio.sleep(0.01)
    task.cancel()
    # Wait until the close is genuinely in flight, then cancel again on top of it
    await asyncio.wait_for(close_started.wait(), timeout=1)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    pesu._csrf_lock.release()

    await asyncio.wait_for(close_finished.wait(), timeout=1)
    new_client.aclose.assert_awaited_once()
    assert pesu._client is None
