"""Unit tests for app/pesu.py — PESUAcademy class (mobile-API implementation)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.exceptions.authentication import AuthenticationError
from app.pesu import BRANCH_MAPPING, PROGRAM_MAPPING, PESUAcademy, _get_semester_from_class


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def pesu():
    return PESUAcademy()


# ---------------------------------------------------------------------------
# _get_semester_from_class (module-level helper)
# ---------------------------------------------------------------------------


def test_get_semester_from_class_sem_prefix():
    assert _get_semester_from_class("Semester 3", None) == "Sem-3"
    assert _get_semester_from_class("Sem-5", None) == "Sem-5"
    assert _get_semester_from_class("Sem 2", None) == "Sem-2"


def test_get_semester_from_class_suffix():
    assert _get_semester_from_class("4th Sem", None) == "Sem-4"
    assert _get_semester_from_class("6 Sem", None) == "Sem-6"


def test_get_semester_from_class_bare_digit():
    assert _get_semester_from_class("7", None) == "Sem-7"


def test_get_semester_from_class_falls_back_to_batch_class():
    assert _get_semester_from_class(None, "Sem-8") == "Sem-8"
    assert _get_semester_from_class(None, "3") == "Sem-3"


def test_get_semester_from_class_both_none():
    assert _get_semester_from_class(None, None) is None


def test_get_semester_from_class_class_name_preferred():
    # class_name wins over batch_class
    assert _get_semester_from_class("Sem-2", "Sem-8") == "Sem-2"


# ---------------------------------------------------------------------------
# PROGRAM_MAPPING / BRANCH_MAPPING constants
# ---------------------------------------------------------------------------


def test_program_mapping_keys():
    assert "B.Tech." in PROGRAM_MAPPING
    assert "M.Tech." in PROGRAM_MAPPING
    assert PROGRAM_MAPPING["B.Tech."] == "Bachelor of Technology"
    assert PROGRAM_MAPPING["MBA"] == "Master of Business Administration"


def test_branch_mapping_keys():
    assert "CSE" in BRANCH_MAPPING
    assert "ECE" in BRANCH_MAPPING
    assert BRANCH_MAPPING["CSE"] == "Computer Science and Engineering"


# ---------------------------------------------------------------------------
# PESUAcademy.DEFAULT_FIELDS
# ---------------------------------------------------------------------------


def test_default_fields_is_list():
    assert isinstance(PESUAcademy.DEFAULT_FIELDS, list)
    expected = [
        "name", "prn", "srn", "program", "branch", "semester",
        "section", "email", "phone", "campusCode", "campus",
        "cycle", "department", "instituteName",
    ]
    for field in expected:
        assert field in PESUAcademy.DEFAULT_FIELDS, f"'{field}' missing from DEFAULT_FIELDS"


def test_default_fields_includes_kycas_relevant_fields():
    """DEFAULT_FIELDS must include fields relevant to KYCAS filtering."""
    fields = PESUAcademy.DEFAULT_FIELDS
    assert "semester" in fields
    assert "cycle" in fields
    assert "department" in fields
    assert "instituteName" in fields


# ---------------------------------------------------------------------------
# PESUAcademy._parse_sslc_name
# ---------------------------------------------------------------------------


def test_parse_sslc_name_returns_none_for_non_dict(pesu):
    assert pesu._parse_sslc_name(None) is None
    assert pesu._parse_sslc_name("string") is None
    assert pesu._parse_sslc_name([]) is None


def test_parse_sslc_name_returns_none_when_list_has_no_dicts(pesu):
    data = {"subject": ["not a dict", 42]}
    assert pesu._parse_sslc_name(data) is None


def test_parse_sslc_name_returns_none_when_name_missing(pesu):
    data = {"subject": [{"Score": 90}]}
    assert pesu._parse_sslc_name(data) is None


def test_parse_sslc_name_returns_none_when_name_empty(pesu):
    data = {"subject": [{"NameAsInSSLC": "   "}]}
    assert pesu._parse_sslc_name(data) is None


def test_parse_sslc_name_returns_stripped_name(pesu):
    data = {"subject": [{"NameAsInSSLC": "  John Doe  "}]}
    assert pesu._parse_sslc_name(data) == "John Doe"


def test_parse_sslc_name_picks_first_non_empty(pesu):
    data = {
        "sub1": [{"NameAsInSSLC": "  "}],
        "sub2": [{"NameAsInSSLC": "Jane Doe"}],
    }
    result = pesu._parse_sslc_name(data)
    assert result == "Jane Doe"


# ---------------------------------------------------------------------------
# PESUAcademy._fetch_name_as_in_sslc
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_name_as_in_sslc_returns_none_on_http_error(pesu):
    client = AsyncMock()
    client.post.side_effect = Exception("Connection error")
    result = await pesu._fetch_name_as_in_sslc(client, "token", "user123")
    assert result is None


@pytest.mark.asyncio
async def test_fetch_name_as_in_sslc_returns_none_on_non_200_sem(pesu):
    client = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    client.post.return_value = mock_resp
    result = await pesu._fetch_name_as_in_sslc(client, "token", "user123")
    assert result is None


@pytest.mark.asyncio
async def test_fetch_name_as_in_sslc_returns_none_when_sem_data_empty(pesu):
    client = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = []
    client.post.return_value = mock_resp
    result = await pesu._fetch_name_as_in_sslc(client, "token", "user123")
    assert result is None


@pytest.mark.asyncio
async def test_fetch_name_as_in_sslc_returns_none_when_sem_data_not_list(pesu):
    client = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"not": "a list"}
    client.post.return_value = mock_resp
    result = await pesu._fetch_name_as_in_sslc(client, "token", "user123")
    assert result is None


@pytest.mark.asyncio
async def test_fetch_name_as_in_sslc_returns_none_when_ids_missing(pesu):
    client = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [{"BatchClassId": None, "ClassBatchSectionId": None}]
    client.post.return_value = mock_resp
    result = await pesu._fetch_name_as_in_sslc(client, "token", "user123")
    assert result is None


@pytest.mark.asyncio
async def test_fetch_name_as_in_sslc_returns_none_on_non_200_results(pesu):
    client = AsyncMock()
    sem_resp = MagicMock()
    sem_resp.status_code = 200
    sem_resp.json.return_value = [{"BatchClassId": 1, "ClassBatchSectionId": 2}]

    results_resp = MagicMock()
    results_resp.status_code = 403
    results_resp.json.return_value = {}

    client.post.side_effect = [sem_resp, results_resp]
    result = await pesu._fetch_name_as_in_sslc(client, "token", "user123")
    assert result is None


@pytest.mark.asyncio
async def test_fetch_name_as_in_sslc_happy_path(pesu):
    client = AsyncMock()
    sem_resp = MagicMock()
    sem_resp.status_code = 200
    sem_resp.json.return_value = [{"BatchClassId": 10, "ClassBatchSectionId": 20}]

    results_resp = MagicMock()
    results_resp.status_code = 200
    results_resp.json.return_value = {"Math": [{"NameAsInSSLC": "Alice Smith", "Score": 95}]}

    client.post.side_effect = [sem_resp, results_resp]
    result = await pesu._fetch_name_as_in_sslc(client, "tok", "u1")
    assert result == "Alice Smith"


# ---------------------------------------------------------------------------
# PESUAcademy._map_data
# ---------------------------------------------------------------------------


def _sample_data(overrides=None):
    base = {
        "loginId": "PES1201800001",
        "departmentId": "PES1UG19CS001",
        "className": "Sem-4",
        "batchClass": None,
        "program": "B.Tech.",
        "branch": "CSE",
        "sectionName": "A",
        "email": "test@example.com",
        "phone": "9876543210",
        "name": "Fallback Name",
    }
    if overrides:
        base.update(overrides)
    return base


def test_map_data_status_and_message(pesu):
    result = pesu._map_data(
        _sample_data(), "user", profile=False,
        know_your_class_and_section=False, fields=[], field_filtering=False
    )
    assert result["status"] is True
    assert result["message"] == "Login successful."


def test_map_data_no_profile_no_kycas(pesu):
    result = pesu._map_data(
        _sample_data(), "user", profile=False,
        know_your_class_and_section=False, fields=[], field_filtering=False
    )
    assert "profile" not in result
    assert "knowYourClassAndSection" not in result


def test_map_data_profile_included(pesu):
    result = pesu._map_data(
        _sample_data(), "user", profile=True,
        know_your_class_and_section=False, fields=[], field_filtering=False
    )
    assert "profile" in result
    profile = result["profile"]
    assert profile["prn"] == "PES1201800001"
    assert profile["srn"] == "PES1UG19CS001"
    assert profile["program"] == "Bachelor of Technology"
    assert profile["branch"] == "Computer Science and Engineering"
    assert profile["semester"] == "Sem-4"
    assert profile["section"] == "A"
    assert profile["email"] == "test@example.com"
    assert profile["phone"] == "9876543210"
    assert profile["campusCode"] == 1
    assert profile["campus"] == "RR"


def test_map_data_campus_code_ec(pesu):
    data = _sample_data({"loginId": "PES2202100001"})
    result = pesu._map_data(
        data, "user", profile=True,
        know_your_class_and_section=False, fields=[], field_filtering=False
    )
    assert result["profile"]["campusCode"] == 2
    assert result["profile"]["campus"] == "EC"


def test_map_data_campus_code_unknown(pesu):
    """For a PRN with an unrecognised campus digit (e.g. PES3…), campus is None
    but campusCode still receives the parsed integer from the regex."""
    data = _sample_data({"loginId": "PES3202100001"})
    result = pesu._map_data(
        data, "user", profile=True,
        know_your_class_and_section=False, fields=[], field_filtering=False
    )
    # campusCode is set to the parsed digit (3) even when the campus name is unknown
    assert result["profile"]["campusCode"] == 3
    assert result["profile"]["campus"] is None


def test_map_data_name_sslc_takes_priority(pesu):
    result = pesu._map_data(
        _sample_data(), "user", profile=True,
        know_your_class_and_section=False, fields=[], field_filtering=False,
        name_sslc="Official Name"
    )
    assert result["profile"]["name"] == "Official Name"


def test_map_data_fallback_to_data_name(pesu):
    result = pesu._map_data(
        _sample_data(), "user", profile=True,
        know_your_class_and_section=False, fields=[], field_filtering=False,
        name_sslc=None
    )
    assert result["profile"]["name"] == "Fallback Name"


def test_map_data_profile_field_filtering(pesu):
    result = pesu._map_data(
        _sample_data(), "user", profile=True,
        know_your_class_and_section=False, fields=["name", "email"], field_filtering=True
    )
    profile = result["profile"]
    assert "name" in profile
    assert "email" in profile
    assert "prn" not in profile
    assert "branch" not in profile


def test_map_data_kycas_included(pesu):
    result = pesu._map_data(
        _sample_data(), "user", profile=False,
        know_your_class_and_section=True, fields=[], field_filtering=False
    )
    assert "knowYourClassAndSection" in result
    kycas = result["knowYourClassAndSection"]
    assert kycas["prn"] == "PES1201800001"
    assert kycas["srn"] == "PES1UG19CS001"
    assert kycas["semester"] == "Sem-4"
    assert kycas["section"] == "Section A"
    assert kycas["cycle"] == "NA"
    assert kycas["instituteName"] == "PES University"
    assert kycas["branch"] == "CSE"
    assert kycas["department"] == "CSE"


def test_map_data_kycas_section_none_when_no_section_name(pesu):
    data = _sample_data({"sectionName": None})
    result = pesu._map_data(
        data, "user", profile=False,
        know_your_class_and_section=True, fields=[], field_filtering=False
    )
    assert result["knowYourClassAndSection"]["section"] is None


def test_map_data_kycas_field_filtering(pesu):
    result = pesu._map_data(
        _sample_data(), "user", profile=False,
        know_your_class_and_section=True, fields=["name", "semester"], field_filtering=True
    )
    kycas = result["knowYourClassAndSection"]
    assert "name" in kycas
    assert "semester" in kycas
    assert "prn" not in kycas
    assert "instituteName" not in kycas


def test_map_data_both_profile_and_kycas(pesu):
    result = pesu._map_data(
        _sample_data(), "user", profile=True,
        know_your_class_and_section=True, fields=[], field_filtering=False
    )
    assert "profile" in result
    assert "knowYourClassAndSection" in result


def test_map_data_srn_falls_back_to_username_when_department_id_missing(pesu):
    data = _sample_data({"departmentId": None})
    result = pesu._map_data(
        data, "myusername", profile=True,
        know_your_class_and_section=False, fields=[], field_filtering=False
    )
    assert result["profile"]["srn"] == "myusername"


# ---------------------------------------------------------------------------
# PESUAcademy.authenticate — error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_authenticate_connection_failure_raises_authentication_error(pesu):
    with patch("app.pesu.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post.side_effect = Exception("Connection refused")
        mock_client_cls.return_value = mock_client

        with pytest.raises(AuthenticationError) as exc_info:
            await pesu.authenticate("user", "pass")
        assert "Connection failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_authenticate_non_200_response_raises_authentication_error(pesu):
    with patch("app.pesu.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value = mock_client

        with pytest.raises(AuthenticationError) as exc_info:
            await pesu.authenticate("user", "pass")
        assert "status code 403" in str(exc_info.value)


@pytest.mark.asyncio
async def test_authenticate_invalid_json_response_raises_authentication_error(pesu):
    with patch("app.pesu.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = Exception("Invalid JSON")
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value = mock_client

        with pytest.raises(AuthenticationError) as exc_info:
            await pesu.authenticate("user", "pass")
        assert "Invalid JSON response" in str(exc_info.value)


@pytest.mark.asyncio
async def test_authenticate_login_not_success_raises_authentication_error(pesu):
    with patch("app.pesu.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "login": "FAILURE",
            "errorMessage": "Invalid username or password",
        }
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value = mock_client

        with pytest.raises(AuthenticationError) as exc_info:
            await pesu.authenticate("user", "wrongpass")
        assert "Invalid username or password" in str(exc_info.value)


@pytest.mark.asyncio
async def test_authenticate_login_not_dict_raises_authentication_error(pesu):
    with patch("app.pesu.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = ["unexpected", "list"]
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value = mock_client

        with pytest.raises(AuthenticationError):
            await pesu.authenticate("user", "pass")


@pytest.mark.asyncio
async def test_authenticate_nested_json_string_parsed(pesu):
    """If response.json() returns a string, it should be re-parsed as JSON."""
    import json as _json

    inner = {"login": "FAILURE", "errorMessage": "Nested error"}

    with patch("app.pesu.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _json.dumps(inner)
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value = mock_client

        with pytest.raises(AuthenticationError) as exc_info:
            await pesu.authenticate("user", "pass")
        assert "Nested error" in str(exc_info.value)


@pytest.mark.asyncio
async def test_authenticate_invalid_nested_json_raises_error(pesu):
    with patch("app.pesu.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = "this is not valid { json"
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value = mock_client

        with pytest.raises(AuthenticationError) as exc_info:
            await pesu.authenticate("user", "pass")
        assert "Invalid nested JSON" in str(exc_info.value)


# ---------------------------------------------------------------------------
# PESUAcademy.authenticate — success paths
# ---------------------------------------------------------------------------


def _make_successful_client(overrides=None, token="tok123", user_id="42"):
    """Return a mock httpx.AsyncClient context manager for a successful login."""
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    data = {
        "login": "SUCCESS",
        "userId": int(user_id) if user_id else None,
        "loginId": "PES1201800001",
        "departmentId": "PES1UG19CS001",
        "className": "Sem-4",
        "batchClass": None,
        "program": "B.Tech.",
        "branch": "CSE",
        "sectionName": "A",
        "email": "test@example.com",
        "phone": "9876543210",
        "name": "Test User",
    }
    if overrides:
        data.update(overrides)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = data
    mock_response.headers = {"mobileappauthenticationtoken": token}
    mock_client.post.return_value = mock_response
    return mock_client


@pytest.mark.asyncio
async def test_authenticate_success_no_profile_no_kycas(pesu):
    with patch("app.pesu.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _make_successful_client()
        result = await pesu.authenticate("user", "pass")
    assert result["status"] is True
    assert result["message"] == "Login successful."
    assert "profile" not in result
    assert "knowYourClassAndSection" not in result


@pytest.mark.asyncio
async def test_authenticate_success_with_profile(pesu):
    with patch("app.pesu.httpx.AsyncClient") as mock_cls:
        mock_client = _make_successful_client()
        mock_cls.return_value = mock_client
        with patch.object(pesu, "_fetch_name_as_in_sslc", new=AsyncMock(return_value=None)):
            result = await pesu.authenticate("user", "pass", profile=True)
    assert result["status"] is True
    assert "profile" in result
    assert result["profile"]["prn"] == "PES1201800001"
    assert result["profile"]["branch"] == "Computer Science and Engineering"


@pytest.mark.asyncio
async def test_authenticate_success_with_profile_field_filtering(pesu):
    with patch("app.pesu.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _make_successful_client()
        with patch.object(pesu, "_fetch_name_as_in_sslc", new=AsyncMock(return_value=None)):
            result = await pesu.authenticate("user", "pass", profile=True, fields=["name", "email"])
    assert "profile" in result
    profile = result["profile"]
    assert "name" in profile
    assert "email" in profile
    assert "prn" not in profile
    assert "branch" not in profile


@pytest.mark.asyncio
async def test_authenticate_success_with_kycas(pesu):
    with patch("app.pesu.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _make_successful_client()
        with patch.object(pesu, "_fetch_name_as_in_sslc", new=AsyncMock(return_value=None)):
            result = await pesu.authenticate("user", "pass", know_your_class_and_section=True)
    assert result["status"] is True
    assert "knowYourClassAndSection" in result
    kycas = result["knowYourClassAndSection"]
    assert kycas["prn"] == "PES1201800001"
    assert kycas["instituteName"] == "PES University"


@pytest.mark.asyncio
async def test_authenticate_success_with_profile_and_kycas(pesu):
    with patch("app.pesu.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _make_successful_client()
        with patch.object(pesu, "_fetch_name_as_in_sslc", new=AsyncMock(return_value=None)):
            result = await pesu.authenticate(
                "user", "pass", profile=True, know_your_class_and_section=True
            )
    assert "profile" in result
    assert "knowYourClassAndSection" in result


@pytest.mark.asyncio
async def test_authenticate_success_with_kycas_field_filtering(pesu):
    with patch("app.pesu.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _make_successful_client()
        with patch.object(pesu, "_fetch_name_as_in_sslc", new=AsyncMock(return_value=None)):
            result = await pesu.authenticate(
                "user", "pass", know_your_class_and_section=True, fields=["name", "semester"]
            )
    kycas = result["knowYourClassAndSection"]
    assert "name" in kycas
    assert "semester" in kycas
    assert "prn" not in kycas
    assert "instituteName" not in kycas


@pytest.mark.asyncio
async def test_authenticate_no_profile_no_kycas_skips_name_fetch(pesu):
    """When no profile or kycas requested, _fetch_name_as_in_sslc must NOT be called."""
    with patch("app.pesu.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _make_successful_client()
        with patch.object(pesu, "_fetch_name_as_in_sslc", new=AsyncMock()) as mock_fetch:
            await pesu.authenticate("user", "pass")
    mock_fetch.assert_not_called()


@pytest.mark.asyncio
async def test_authenticate_uses_name_sslc_when_available(pesu):
    with patch("app.pesu.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _make_successful_client()
        with patch.object(pesu, "_fetch_name_as_in_sslc", new=AsyncMock(return_value="Official Name")):
            result = await pesu.authenticate("user", "pass", profile=True)
    assert result["profile"]["name"] == "Official Name"


@pytest.mark.asyncio
async def test_authenticate_no_token_skips_sslc_fetch(pesu):
    """If the response header has no token, _fetch_name_as_in_sslc is skipped."""
    with patch("app.pesu.httpx.AsyncClient") as mock_cls:
        mock_client = _make_successful_client(token="")
        mock_cls.return_value = mock_client
        with patch.object(pesu, "_fetch_name_as_in_sslc", new=AsyncMock()) as mock_fetch:
            result = await pesu.authenticate("user", "pass", profile=True)
    mock_fetch.assert_not_called()
    assert result["profile"]["name"] == "Test User"  # fallback from data


@pytest.mark.asyncio
async def test_authenticate_fields_defaults_to_default_fields(pesu):
    """When fields=None, field_filtering should be False (all fields returned)."""
    with patch("app.pesu.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _make_successful_client()
        with patch.object(pesu, "_fetch_name_as_in_sslc", new=AsyncMock(return_value=None)):
            result = await pesu.authenticate("user", "pass", profile=True, fields=None)
    profile = result["profile"]
    # No field filtering → all profile keys present
    for key in ["name", "prn", "srn", "branch", "semester", "section", "email", "phone"]:
        assert key in profile, f"'{key}' unexpectedly missing"


@pytest.mark.asyncio
async def test_authenticate_custom_fields_triggers_field_filtering(pesu):
    """When fields differ from DEFAULT_FIELDS, field_filtering=True applies."""
    with patch("app.pesu.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _make_successful_client()
        with patch.object(pesu, "_fetch_name_as_in_sslc", new=AsyncMock(return_value=None)):
            result = await pesu.authenticate("user", "pass", profile=True, fields=["prn"])
    profile = result["profile"]
    assert "prn" in profile
    assert "name" not in profile
