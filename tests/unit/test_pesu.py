"""Tests for PESUAcademy against a mocked PESU Academy mobile API."""

import asyncio

import httpx2
import pytest

from app.exceptions.authentication import (
    AuthenticationError,
    ProfileFetchError,
    ProfileParseError,
    UpstreamError,
)
from app.metrics.collector import (
    HTTP_CLIENTS,
    PROFILE_PARSE_ERRORS,
    UPSTREAM_REQUESTS,
    UPSTREAM_RESPONSES,
    MetricsCollector,
)
from app.models import ProfileModel
from app.pesu import _CLOSE_TASKS, DISPATCHER_URL, LOGIN_URL, PESUAcademy, _as_prn, _as_srn, _upstream_call

FULL_PROFILE = {
    "name": "JOHN DOE",
    "prn": "PES2202500001",
    "srn": "PES2UG25CS001",
    "program": "B.Tech.",
    "branch": "Computer Science and Engineering",
    "semester": "Sem-4",
    "section": "Section C",
    "email": "john.doe@example.com",
    "phone": "9876543210",
    "campusCode": 2,
    "campus": "EC",
    "firstName": "JOHN",
    "middleName": None,
    "lastName": "DOE",
    "branchShortCode": "CSE",
    "institute": "PES University (Electronic City)",
    "rollNumber": 27,
    "gender": "Male",
    # Midnight IST on 2005-01-01; read in UTC it would be 2004-12-31
    "dateOfBirth": "2005-01-01",
}


@pytest.fixture
def collector():
    return MetricsCollector(clock=lambda: 1000.0)


@pytest.fixture
def pesu(collector):
    return PESUAcademy(collector)


@pytest.fixture
def login_ok(upstream, make_response, login_payload):
    """Upstream that accepts the login and is not asked for a profile."""
    upstream.side_effect = [make_response(json=login_payload)]
    return upstream


async def _profile_for(pesu, upstream, make_response, login_payload, profile_payload):
    upstream.side_effect = [make_response(json=login_payload), make_response(json=profile_payload)]
    result = await pesu.authenticate("user", "pass", profile=True)
    return result["profile"]


def _clients(collector):
    snapshot = collector.snapshot()
    return {event: snapshot.value(HTTP_CLIENTS.name, event=event) for event in ("created", "closed")}


# --- Login ---


@pytest.mark.asyncio
async def test_login_without_profile_makes_one_call(pesu, login_ok):
    result = await pesu.authenticate("user", "pass")

    assert result == {"status": True, "message": "Login successful."}
    login_ok.assert_awaited_once()


@pytest.mark.asyncio
async def test_login_sends_the_mobile_app_form(pesu, login_ok):
    await pesu.authenticate("PES2UG25CS001", "pass")

    call = login_ok.await_args
    assert call.args == (LOGIN_URL,)
    assert call.kwargs["headers"] == {"X-Client-Type": "MOBILE"}
    # Multipart fields, not url-encoded data: that is what the endpoint accepts
    assert call.kwargs["files"] == {
        "userName": (None, "PES2UG25CS001"),
        "password": (None, "pass"),
        "j_appId": (None, "YES"),
        "instId": (None, "1,6,7,14"),
    }


@pytest.mark.asyncio
async def test_rejected_credentials_are_an_authentication_error(pesu, upstream, make_response):
    # What PESU sends for both a wrong password and an unknown user
    upstream.side_effect = [
        make_response(401, json={"statusCode": 401, "statusDescription": "Invalid Login Credentials"}),
    ]

    with pytest.raises(AuthenticationError) as exc_info:
        await pesu.authenticate("user", "wrong", profile=True)

    assert exc_info.value.status_code == 401
    # No profile call after a failed login
    upstream.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("marker", ["FAILURE", "success", "NA", None, "missing"])
async def test_a_200_that_is_not_a_success_is_an_upstream_error(pesu, upstream, make_response, login_payload, marker):
    """Only an HTTP 401 means rejected credentials; any other non-success is PESU answering unexpectedly."""
    if marker == "missing":
        del login_payload["mobileJsonObject"]["login"]
    else:
        login_payload["mobileJsonObject"]["login"] = marker
    upstream.side_effect = [make_response(json=login_payload)]

    with pytest.raises(UpstreamError) as exc_info:
        await pesu.authenticate("user", "pass", profile=True)

    assert exc_info.value.status_code == 502
    # No profile call after a login that did not succeed
    upstream.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [403, 500, 503])
async def test_any_other_login_status_is_an_upstream_error(pesu, upstream, make_response, status):
    upstream.side_effect = [make_response(status, content=b"<html>error</html>")]

    with pytest.raises(UpstreamError) as exc_info:
        await pesu.authenticate("user", "pass")

    assert exc_info.value.status_code == 502
    assert str(status) in exc_info.value.message


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        b"<html>not json</html>",
        b'{"status": 200}',
        b'{"mobileJsonObject": "not an object"}',
        b'"a json string"',
    ],
)
async def test_an_unexpected_login_response_is_an_upstream_error(pesu, upstream, make_response, body):
    upstream.side_effect = [make_response(content=body)]

    with pytest.raises(UpstreamError) as exc_info:
        await pesu.authenticate("user", "pass")

    # Not chained: a ValidationError's message would quote the response
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__suppress_context__ is True


@pytest.mark.asyncio
async def test_an_unreachable_login_is_an_upstream_error(pesu, upstream):
    upstream.side_effect = httpx2.ConnectError("connection refused")

    with pytest.raises(UpstreamError) as exc_info:
        await pesu.authenticate("user", "pass")

    assert isinstance(exc_info.value.__cause__, httpx2.ConnectError)


@pytest.mark.asyncio
async def test_a_login_without_a_token_cannot_fetch_the_profile(pesu, upstream, make_response, login_payload):
    del login_payload["accessToken"]
    upstream.side_effect = [make_response(json=login_payload)]

    with pytest.raises(UpstreamError):
        await pesu.authenticate("user", "pass", profile=True)

    upstream.assert_awaited_once()


@pytest.mark.asyncio
async def test_a_login_without_a_token_is_fine_without_a_profile(pesu, upstream, make_response, login_payload):
    del login_payload["accessToken"]
    upstream.side_effect = [make_response(json=login_payload)]

    result = await pesu.authenticate("user", "pass")

    assert result["status"] is True


# --- Profile fetch ---


@pytest.mark.asyncio
async def test_profile_is_built_from_both_responses(pesu, upstream, make_response, login_payload, profile_payload):
    profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    assert profile == FULL_PROFILE
    # And it is something the response model accepts
    ProfileModel.model_validate(profile)


@pytest.mark.asyncio
async def test_profile_call_uses_the_login_token(pesu, upstream, make_response, login_payload, profile_payload):
    await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    call = upstream.await_args_list[1]
    assert call.args == (DISPATCHER_URL,)
    assert call.kwargs["headers"] == {"X-Client-Type": "MOBILE", "Authorization": "Bearer ACCESS-TOKEN-SECRET"}
    assert call.kwargs["files"] == {"action": (None, "27"), "mode": (None, "1"), "menuId": (None, "11172")}


@pytest.mark.asyncio
async def test_a_failed_profile_status_is_a_fetch_error(pesu, upstream, make_response, login_payload):
    upstream.side_effect = [make_response(json=login_payload), make_response(500, content=b"oops")]

    with pytest.raises(ProfileFetchError) as exc_info:
        await pesu.authenticate("user", "pass", profile=True)

    assert exc_info.value.status_code == 502


@pytest.mark.asyncio
async def test_an_unreachable_profile_is_a_fetch_error(pesu, upstream, make_response, login_payload):
    upstream.side_effect = [make_response(json=login_payload), httpx2.ReadTimeout("timed out")]

    with pytest.raises(ProfileFetchError):
        await pesu.authenticate("user", "pass", profile=True)


@pytest.mark.asyncio
async def test_a_declined_profile_is_a_fetch_error(pesu, upstream, make_response, login_payload, profile_payload):
    profile_payload["MESSAGE"] = "FAILURE_Record not found"
    upstream.side_effect = [make_response(json=login_payload), make_response(json=profile_payload)]

    with pytest.raises(ProfileFetchError):
        await pesu.authenticate("user", "pass", profile=True)


@pytest.mark.asyncio
async def test_a_profile_without_student_info_is_built_from_student_photo(
    pesu, upstream, make_response, login_payload, profile_payload
):
    """The shape recorded in issue #233: only STUDENT_PHOTO, with the SRN under loginId."""
    del profile_payload["STUDENT_INFO"]

    profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    assert profile == {
        **FULL_PROFILE,
        # Only STUDENT_INFO has the branch and its short code; the login's "Branch:CSE" is not parsed
        "branch": None,
        "branchShortCode": None,
        "lastName": None,
    }


@pytest.mark.asyncio
async def test_student_photo_fills_the_gaps_in_student_info(
    pesu, upstream, make_response, login_payload, profile_payload
):
    login_payload["mobileJsonObject"].update(email=None, phone=None)
    profile_payload["STUDENT_INFO"].update(SRN=None, NameAsInSSLC=None, Email=None, Mobile=None)
    profile_payload["STUDENT_PHOTO"].update(email="photo@example.com", mobile="5554443332")

    profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    assert profile["srn"] == "PES2UG25CS001"
    assert profile["name"] == "JOHN DOE"
    assert profile["email"] == "photo@example.com"
    assert profile["phone"] == "5554443332"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        b"<html>not json</html>",
        b'{"MESSAGE": "SUCCESS_Record found Successfully"}',
        # PESU sends {} for an empty block; with every field optional it must not pass as a student
        b'{"MESSAGE": "SUCCESS_Record found Successfully", "STUDENT_INFO": {}, "STUDENT_PHOTO": {}}',
        b'{"MESSAGE": "SUCCESS_Record found Successfully", "STUDENT_INFO": {"SomethingNew": "x"}}',
        b'{"MESSAGE": "SUCCESS_Record found Successfully", "STUDENT_INFO": {"SRN": null, "Email": "NA"}}',
        # Not PESU's error envelope: a status of 200 is not an error
        b'{"status": 200, "message": "OK"}',
    ],
    ids=["not json", "no student", "empty blocks", "unknown keys only", "only empty values", "status 200"],
)
async def test_an_unexpected_profile_response_is_a_parse_error(
    pesu, upstream, make_response, login_payload, collector, body
):
    upstream.side_effect = [make_response(json=login_payload), make_response(content=body)]

    with pytest.raises(ProfileParseError) as exc_info:
        await pesu.authenticate("user", "pass", profile=True)

    assert exc_info.value.status_code == 422
    assert exc_info.value.__cause__ is None
    assert collector.snapshot().value(PROFILE_PARSE_ERRORS.name, reason="response_structure") == 1.0


@pytest.mark.asyncio
async def test_an_error_envelope_from_the_dispatcher_is_a_fetch_error(
    pesu, upstream, make_response, login_payload, collector
):
    """What the dispatcher answers, with an HTTP 200, to a request it rejects. PESU failed, so a 502."""
    envelope = {"status": 400, "message": "Invalid request", "errorCode": None, "timestamp": 1}
    upstream.side_effect = [make_response(json=login_payload), make_response(json=envelope)]

    with pytest.raises(ProfileFetchError) as exc_info:
        await pesu.authenticate("user", "pass", profile=True)

    assert exc_info.value.status_code == 502
    assert "error status 400" in exc_info.value.message
    # PESU's own text is not forwarded to the caller
    assert "Invalid request" not in exc_info.value.message
    assert exc_info.value.__cause__ is None
    # Not a parse failure: the API has not changed shape, PESU said no
    assert collector.snapshot().value(PROFILE_PARSE_ERRORS.name, reason="response_structure") == 0.0


@pytest.mark.asyncio
async def test_one_block_with_data_is_enough(pesu, upstream, make_response, login_payload, profile_payload):
    profile_payload["STUDENT_INFO"] = {}

    profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    assert profile["srn"] == "PES2UG25CS001"
    assert profile["name"] == "JOHN DOE"


# --- Mapping ---


@pytest.mark.asyncio
async def test_without_the_full_name_the_name_is_null(pesu, upstream, make_response, login_payload, profile_payload):
    """The login's name is the first name only, so it is not passed off as the full name."""
    profile_payload["STUDENT_INFO"]["NameAsInSSLC"] = None
    profile_payload["STUDENT_PHOTO"]["nameAsInSSLC"] = None

    profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    assert profile["name"] is None
    assert profile["firstName"] == "JOHN"


@pytest.mark.asyncio
async def test_a_student_without_a_class_has_no_semester_or_section(
    pesu, upstream, make_response, login_payload, profile_payload
):
    """What a graduated student looks like: no class, no section, no program or branch either."""
    user = login_payload["mobileJsonObject"]
    user.update(className=None, sectionName=None, program=None, branch=None)
    profile_payload["STUDENT_INFO"].update(ProgramAbbreviation=None, Branch=None)

    profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    for field in ("semester", "section", "program", "branch"):
        assert profile[field] is None


@pytest.mark.asyncio
async def test_class_and_section_fall_back_to_the_profile_response(
    pesu, upstream, make_response, login_payload, profile_payload
):
    login_payload["mobileJsonObject"].update(className=None, sectionName=None)
    profile_payload["STUDENT_INFO"].update(ClassName="Sem-6", SectionName="Section A")

    profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    assert profile["semester"] == "Sem-6"
    assert profile["section"] == "Section A"


@pytest.mark.asyncio
@pytest.mark.parametrize("class_name", ["", "   ", ", Section C"])
async def test_a_blank_class_name_has_no_semester(
    pesu, upstream, make_response, login_payload, profile_payload, class_name
):
    login_payload["mobileJsonObject"]["className"] = class_name

    profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    assert profile["semester"] is None


@pytest.mark.asyncio
async def test_na_placeholders_are_treated_as_missing(pesu, upstream, make_response, login_payload, profile_payload):
    """The web portal printed "NA" for a student with no class; it is not a semester."""
    login_payload["mobileJsonObject"].update(className="NA", sectionName=" NA ")

    profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    assert profile["semester"] is None
    assert profile["section"] is None


@pytest.mark.asyncio
async def test_blank_values_are_treated_as_missing(pesu, upstream, make_response, login_payload, profile_payload):
    login_payload["mobileJsonObject"].update(email="", phone="  ")

    profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    # Filled from the profile response instead of returned as empty strings
    assert profile["email"] == "john.doe@example.com"
    assert profile["phone"] == "9876543210"


@pytest.mark.asyncio
async def test_contact_details_fall_back_to_the_profile_response(
    pesu, upstream, make_response, login_payload, profile_payload
):
    login_payload["mobileJsonObject"].update(email=None, phone=None)
    profile_payload["STUDENT_INFO"].update(Email="other@example.com", Mobile=9998887776)

    profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    assert profile["email"] == "other@example.com"
    # A number upstream is still a string here, as the model requires
    assert profile["phone"] == "9998887776"


@pytest.mark.asyncio
async def test_an_srn_under_login_id_is_not_returned_as_the_prn(
    pesu, upstream, make_response, login_payload, profile_payload
):
    login_payload["mobileJsonObject"]["loginId"] = "PES2UG25CS001"
    profile_payload["STUDENT_INFO"]["LoginId"] = "PES2UG25CS001"
    profile_payload["USER_ROLE"]["LoginId"] = "PES2UG25CS001"

    profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    assert profile["prn"] is None
    assert profile["srn"] == "PES2UG25CS001"


@pytest.mark.asyncio
async def test_prn_falls_back_to_the_profile_response(pesu, upstream, make_response, login_payload, profile_payload):
    del login_payload["mobileJsonObject"]["loginId"]

    profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    assert profile["prn"] == "PES2202500001"


@pytest.mark.asyncio
async def test_an_older_student_whose_prn_is_their_srn(pesu, upstream, make_response, login_payload, profile_payload):
    """Students admitted before SRNs existed have the PRN in both places."""
    login_payload["mobileJsonObject"]["loginId"] = "PES1201800001"
    profile_payload["STUDENT_INFO"].update(LoginId="PES1201800001", SRN="PES1201800001")

    profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    assert profile["prn"] == profile["srn"] == "PES1201800001"
    assert (profile["campusCode"], profile["campus"]) == (1, "RR")


@pytest.mark.asyncio
async def test_campus_falls_back_to_the_prn(pesu, upstream, make_response, login_payload, profile_payload):
    login_payload["mobileJsonObject"]["loginId"] = "PES1202500001"
    profile_payload["STUDENT_INFO"]["SRN"] = None
    # Without STUDENT_PHOTO too, since its loginId would otherwise stand in for the SRN
    del profile_payload["STUDENT_PHOTO"]

    profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    assert (profile["campusCode"], profile["campus"]) == (1, "RR")


@pytest.mark.asyncio
async def test_no_identifier_means_no_campus(pesu, upstream, make_response, login_payload, profile_payload):
    del login_payload["mobileJsonObject"]["loginId"]
    profile_payload["STUDENT_INFO"].update(LoginId=None, SRN=None)
    del profile_payload["STUDENT_PHOTO"]
    del profile_payload["USER_ROLE"]

    profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    for field in ("prn", "srn", "campusCode", "campus"):
        assert profile[field] is None


@pytest.mark.asyncio
async def test_an_unknown_campus_code_is_counted_not_fatal(
    pesu, upstream, make_response, login_payload, profile_payload, collector, caplog
):
    profile_payload["STUDENT_INFO"]["SRN"] = "PES3UG25CS001"

    with caplog.at_level("WARNING"):
        profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    assert profile["srn"] == "PES3UG25CS001"
    assert profile["campus"] is None
    assert profile["campusCode"] is None
    assert collector.snapshot().value(PROFILE_PARSE_ERRORS.name, reason="unknown_campus_code") == 1.0
    assert "Unknown campus code: 3" in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("program", ["B.Tech.", "M.Tech", "MCA", "B.Sc.(Hons)"])
async def test_the_program_is_returned_as_pesu_writes_it(
    pesu, upstream, make_response, login_payload, profile_payload, collector, program
):
    """No expansion: a full name would be our guess, and a wrong guess would be served as fact."""
    login_payload["mobileJsonObject"]["program"] = program

    profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    assert profile["program"] == program
    assert list(collector.snapshot().samples(PROFILE_PARSE_ERRORS.name)) == []


@pytest.mark.asyncio
async def test_program_falls_back_to_the_profile_response(
    pesu, upstream, make_response, login_payload, profile_payload
):
    login_payload["mobileJsonObject"]["program"] = None
    profile_payload["STUDENT_INFO"]["ProgramAbbreviation"] = "MCA"

    profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    assert profile["program"] == "MCA"


# --- Field filtering ---


@pytest.mark.asyncio
async def test_field_filtering(pesu, upstream, make_response, login_payload, profile_payload):
    upstream.side_effect = [make_response(json=login_payload), make_response(json=profile_payload)]

    fields = ["dateOfBirth", "name", "rollNumber", "campus", "middleName", "branchShortCode"]
    result = await pesu.authenticate("user", "pass", profile=True, fields=fields)

    assert result["profile"] == {
        "name": "JOHN DOE",
        "campus": "EC",
        "middleName": None,
        "branchShortCode": "CSE",
        "rollNumber": 27,
        "dateOfBirth": "2005-01-01",
    }
    # In the documented order, whatever order they were asked for in
    assert list(result["profile"]) == [field for field in PESUAcademy.DEFAULT_FIELDS if field in fields]


@pytest.mark.asyncio
async def test_a_requested_field_upstream_does_not_have_is_none(
    pesu, upstream, make_response, login_payload, profile_payload
):
    login_payload["mobileJsonObject"]["className"] = None
    profile_payload["STUDENT_PHOTO"]["gender"] = ""
    upstream.side_effect = [make_response(json=login_payload), make_response(json=profile_payload)]

    result = await pesu.authenticate(
        "user", "pass", profile=True, fields=["semester", "srn", "middleName", "gender", "institute"]
    )

    # Requested, so present; no value, so None
    assert result["profile"] == {
        "srn": "PES2UG25CS001",
        "semester": None,
        "middleName": None,
        "institute": "PES University (Electronic City)",
        "gender": None,
    }


def test_default_fields_are_every_profile_field():
    assert PESUAcademy.DEFAULT_FIELDS == list(FULL_PROFILE)


# --- Client lifecycle ---


@pytest.mark.asyncio
async def test_each_login_gets_its_own_client_and_closes_it(pesu, upstream, make_response, login_payload, collector):
    upstream.side_effect = [make_response(json=login_payload), make_response(json=login_payload)]

    await pesu.authenticate("user", "pass")
    await pesu.authenticate("user", "pass")

    assert _clients(collector) == {"created": 2.0, "closed": 2.0}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (httpx2.ConnectError("down"), UpstreamError),
        (asyncio.CancelledError(), asyncio.CancelledError),
    ],
)
async def test_the_client_is_closed_when_the_login_fails(pesu, upstream, collector, side_effect, error):
    upstream.side_effect = [side_effect]

    with pytest.raises(error):
        await pesu.authenticate("user", "pass")

    assert _clients(collector) == {"created": 1.0, "closed": 1.0}


@pytest.mark.asyncio
async def test_the_client_is_closed_when_the_profile_fails(pesu, upstream, make_response, login_payload, collector):
    upstream.side_effect = [make_response(json=login_payload), make_response(500)]

    with pytest.raises(ProfileFetchError):
        await pesu.authenticate("user", "pass", profile=True)

    assert _clients(collector) == {"created": 1.0, "closed": 1.0}


# --- What is logged ---


@pytest.mark.asyncio
async def test_no_password_token_or_private_data_is_logged(
    pesu, upstream, make_response, login_payload, profile_payload, secrets, caplog
):
    upstream.side_effect = [make_response(json=login_payload), make_response(json=profile_payload)]

    with caplog.at_level("DEBUG"):
        await pesu.authenticate("user", "hunter2-password", profile=True)

    for secret in (*secrets, "hunter2-password"):
        assert secret not in caplog.text


@pytest.mark.asyncio
async def test_an_unparseable_profile_logs_where_not_what(
    pesu, upstream, make_response, login_payload, profile_payload, secrets, caplog
):
    profile_payload["STUDENT_INFO"]["NameAsInSSLC"] = {"unexpected": "FATHERNAMESECRET"}
    upstream.side_effect = [make_response(json=login_payload), make_response(json=profile_payload)]

    with caplog.at_level("DEBUG"), pytest.raises(ProfileParseError) as exc_info:
        await pesu.authenticate("user", "pass", profile=True)

    assert "STUDENT_INFO" in caplog.text
    assert "NameAsInSSLC" in caplog.text
    for secret in secrets:
        assert secret not in caplog.text
        assert secret not in str(exc_info.value)


@pytest.mark.asyncio
async def test_parsed_login_does_not_expose_the_token_in_its_repr(login_payload):
    from app.pesu import _LoginResponse

    login = _LoginResponse.model_validate(login_payload)

    assert login.access_token == "ACCESS-TOKEN-SECRET"
    assert "ACCESS-TOKEN-SECRET" not in repr(login)
    # Fields never declared are never kept
    assert "LOGINPHOTOSECRET" not in repr(login)


# --- More login and profile responses ---


@pytest.mark.asyncio
async def test_a_login_with_a_null_user_is_an_upstream_error(pesu, upstream, make_response):
    upstream.side_effect = [make_response(json={"mobileJsonObject": None, "accessToken": "t"})]

    with pytest.raises(UpstreamError):
        await pesu.authenticate("user", "pass")


@pytest.mark.asyncio
async def test_a_401_is_rejected_credentials_whatever_its_body(pesu, upstream, make_response):
    """Only the status is relied on, so a 401 with an HTML or empty body is still a 401."""
    upstream.side_effect = [make_response(401, content=b"<html>Unauthorized</html>")]

    with pytest.raises(AuthenticationError):
        await pesu.authenticate("user", "wrong")


@pytest.mark.asyncio
@pytest.mark.parametrize("token", ["", "   ", None])
async def test_a_blank_access_token_cannot_fetch_the_profile(pesu, upstream, make_response, login_payload, token):
    login_payload["accessToken"] = token
    upstream.side_effect = [make_response(json=login_payload)]

    with pytest.raises(UpstreamError):
        await pesu.authenticate("user", "pass", profile=True)

    upstream.assert_awaited_once()


@pytest.mark.asyncio
async def test_extra_upstream_fields_are_ignored(pesu, upstream, make_response, login_payload, profile_payload):
    """PESU adding a field must not break parsing; only removing or retyping one we use can."""
    login_payload["mobileJsonObject"]["someNewField"] = {"nested": [1, 2, 3]}
    profile_payload["STUDENT_INFO"]["AnotherNewField"] = "value"
    profile_payload["BRAND_NEW_BLOCK"] = {}

    profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    assert profile == FULL_PROFILE


@pytest.mark.asyncio
async def test_a_retyped_field_we_use_is_a_parse_error(
    pesu, upstream, make_response, login_payload, profile_payload, collector
):
    profile_payload["STUDENT_INFO"]["SRN"] = ["PES2UG25CS001"]
    upstream.side_effect = [make_response(json=login_payload), make_response(json=profile_payload)]

    with pytest.raises(ProfileParseError):
        await pesu.authenticate("user", "pass", profile=True)

    assert collector.snapshot().value(PROFILE_PARSE_ERRORS.name, reason="response_structure") == 1.0


@pytest.mark.parametrize(
    ("login_id", "expected"),
    [
        ("PES1201800001", "PES1201800001"),  # older PRN, also used as the SRN
        ("PES2202500001", "PES2202500001"),  # current PRN
        ("PES2UG25CS001", None),  # an SRN
        ("PES220250000", None),  # one digit short
        ("PES22025000011", None),  # one digit long
        ("pes2202500001", None),  # not how PESU writes it
        ("john.doe@example.com", None),
        (None, None),
    ],
)
def test_only_a_prn_shaped_login_id_is_a_prn(login_id, expected):
    assert _as_prn(login_id) == expected


@pytest.mark.asyncio
async def test_duplicate_requested_fields_are_returned_once(
    pesu, upstream, make_response, login_payload, profile_payload
):
    upstream.side_effect = [make_response(json=login_payload), make_response(json=profile_payload)]

    result = await pesu.authenticate("user", "pass", profile=True, fields=["name", "rollNumber", "name", "rollNumber"])

    assert result["profile"] == {"name": "JOHN DOE", "rollNumber": 27}


@pytest.mark.asyncio
async def test_fields_without_a_profile_are_ignored(pesu, login_ok):
    result = await pesu.authenticate("user", "pass", profile=False, fields=["name", "rollNumber", "dateOfBirth"])

    assert "profile" not in result
    login_ok.assert_awaited_once()


# --- On the wire ---


def _route_logins(wire, make_response, login_payload, profile_payload):
    wire.routes[LOGIN_URL] = lambda request: make_response(json=login_payload)
    wire.routes[DISPATCHER_URL] = lambda request: make_response(json=profile_payload)


def _multipart_fields(request):
    """Decode a multipart request body into {field name: value}."""
    boundary = request.headers["content-type"].split("boundary=")[1].encode()
    fields = {}
    for part in request.content.split(b"--" + boundary):
        if b'name="' not in part:
            continue
        head, _, value = part.partition(b"\r\n\r\n")
        name = head.split(b'name="')[1].split(b'"')[0].decode()
        fields[name] = value.rstrip(b"\r\n").decode()
    return fields


@pytest.mark.asyncio
async def test_the_login_request_on_the_wire(pesu, wire, make_response, login_payload, profile_payload):
    _route_logins(wire, make_response, login_payload, profile_payload)

    await pesu.authenticate("PES2UG25CS001", "hunter2")

    (login,) = wire.requests
    assert login.method == "POST"
    assert str(login.url) == LOGIN_URL
    assert login.headers["x-client-type"] == "MOBILE"
    assert login.headers["content-type"].startswith("multipart/form-data; boundary=")
    # Nothing to authenticate with yet, and nothing from another login
    assert "authorization" not in login.headers
    assert _multipart_fields(login) == {
        "userName": "PES2UG25CS001",
        "password": "hunter2",
        "j_appId": "YES",
        "instId": "1,6,7,14",
    }


@pytest.mark.asyncio
async def test_the_profile_request_on_the_wire(pesu, wire, make_response, login_payload, profile_payload):
    _route_logins(wire, make_response, login_payload, profile_payload)

    await pesu.authenticate("user", "hunter2", profile=True)

    login, dispatcher = wire.requests
    assert str(dispatcher.url) == DISPATCHER_URL
    assert dispatcher.headers["authorization"] == "Bearer ACCESS-TOKEN-SECRET"
    assert dispatcher.headers["x-client-type"] == "MOBILE"
    assert _multipart_fields(dispatcher) == {"action": "27", "mode": "1", "menuId": "11172"}
    # The password goes to the login and nowhere else
    assert b"hunter2" in login.content
    assert b"hunter2" not in dispatcher.content


@pytest.mark.asyncio
async def test_one_client_per_login_with_a_timeout_and_no_redirects(
    pesu, wire, make_response, login_payload, profile_payload
):
    _route_logins(wire, make_response, login_payload, profile_payload)

    await pesu.authenticate("user", "pass", profile=True)
    await pesu.authenticate("user", "pass")

    # Two logins, two clients; the profile call reused its login's client
    assert wire.client_options == [{"timeout": 10.0}, {"timeout": 10.0}]


@pytest.mark.asyncio
async def test_a_redirect_is_not_followed(pesu, wire, make_response):
    """A redirect means something in front of PESU changed; following it could post the password elsewhere."""
    wire.routes[LOGIN_URL] = lambda request: httpx2.Response(302, headers={"location": "https://elsewhere.example/"})

    with pytest.raises(UpstreamError) as exc_info:
        await pesu.authenticate("user", "pass")

    assert "302" in exc_info.value.message
    assert len(wire.requests) == 1


@pytest.mark.asyncio
async def test_a_timeout_is_an_upstream_error(pesu, wire, collector):
    wire.routes[LOGIN_URL] = lambda request: httpx2.ReadTimeout("timed out", request=request)

    with pytest.raises(UpstreamError):
        await pesu.authenticate("user", "pass")

    assert collector.snapshot().value(UPSTREAM_REQUESTS.name, operation="login", outcome="error") == 1.0
    assert _clients(collector) == {"created": 1.0, "closed": 1.0}


# --- Concurrency and cancellation ---


@pytest.mark.asyncio
async def test_concurrent_logins_do_not_share_anything(pesu, upstream, make_response, login_payload, profile_payload):
    """Two students logging in at once each get their own token, profile and client."""
    # token, SRN, name, first name, roll number, date of birth (midnight IST)
    students = {
        "alice": ("TOKEN-ALICE", "PES1UG25CS001", "ALICE A", "ALICE", 11, 1078425000000),
        "bob": ("TOKEN-BOB", "PES2UG25EC002", "BOB B", "BOB", 42, 1069266600000),
    }
    tokens = {details[0]: student for student, details in students.items()}

    async def respond(url, files, headers):
        # Yield first, so the two logins interleave rather than run back to back
        await asyncio.sleep(0)
        if url == LOGIN_URL:
            student = files["userName"][1]
            body = {**login_payload, "accessToken": students[student][0]}
            return make_response(json=body)
        student = tokens[headers["Authorization"].removeprefix("Bearer ")]
        _, srn, name, first_name, roll_number, date_of_birth = students[student]
        info = {
            **profile_payload["STUDENT_INFO"],
            "SRN": srn,
            "NameAsInSSLC": name,
            "FirstName": first_name,
            "DateOfBirth": date_of_birth,
        }
        semesters = [{"studentRollNo": roll_number, "batchClassOrder": 1}]
        return make_response(json={**profile_payload, "STUDENT_INFO": info, "STUDENT_SEMESTERS": semesters})

    upstream.side_effect = respond

    fields = ["name", "srn", "campus", "firstName", "rollNumber", "dateOfBirth"]
    alice, bob = await asyncio.gather(
        pesu.authenticate("alice", "pass", profile=True, fields=fields),
        pesu.authenticate("bob", "pass", profile=True, fields=fields),
    )

    assert alice["profile"] == {
        "name": "ALICE A",
        "srn": "PES1UG25CS001",
        "campus": "RR",
        "firstName": "ALICE",
        "rollNumber": 11,
        "dateOfBirth": "2004-03-05",
    }
    assert bob["profile"] == {
        "name": "BOB B",
        "srn": "PES2UG25EC002",
        "campus": "EC",
        "firstName": "BOB",
        "rollNumber": 42,
        "dateOfBirth": "2003-11-20",
    }


@pytest.mark.asyncio
async def test_a_cancelled_profile_fetch_closes_the_client(pesu, upstream, make_response, login_payload, collector):
    upstream.side_effect = [make_response(json=login_payload), asyncio.CancelledError()]

    with pytest.raises(asyncio.CancelledError):
        await pesu.authenticate("user", "pass", profile=True)

    snapshot = collector.snapshot()
    assert snapshot.value(UPSTREAM_REQUESTS.name, operation="profile_fetch", outcome="cancelled") == 1.0
    assert _clients(collector) == {"created": 1.0, "closed": 1.0}


@pytest.mark.asyncio
async def test_a_cancellation_during_the_close_still_closes(
    pesu, upstream, make_response, login_payload, collector, monkeypatch
):
    """A shutdown can cancel a request that is already closing its client; the close must finish."""
    close_started, release = asyncio.Event(), asyncio.Event()

    async def slow_close(self):
        close_started.set()
        await release.wait()

    monkeypatch.setattr("app.pesu.httpx2.AsyncClient.aclose", slow_close)
    upstream.side_effect = [make_response(json=login_payload)]

    task = asyncio.create_task(pesu.authenticate("user", "pass"))
    await close_started.wait()
    task.cancel()
    release.set()

    with pytest.raises(asyncio.CancelledError):
        await task
    # The shielded close outlives the cancelled request and completes on its own
    while _CLOSE_TASKS:
        await asyncio.sleep(0)
    assert _clients(collector) == {"created": 1.0, "closed": 1.0}


# --- Upstream call accounting ---


@pytest.mark.asyncio
@pytest.mark.parametrize("sink_contents", [[], [object()]])
async def test_an_upstream_call_without_a_status_records_no_status(collector, sink_contents):
    async with _upstream_call(collector, "login") as sink:
        sink.extend(sink_contents)

    snapshot = collector.snapshot()
    assert snapshot.value(UPSTREAM_REQUESTS.name, operation="login", outcome="success") == 1.0
    assert list(snapshot.samples(UPSTREAM_RESPONSES.name)) == []


# --- Profile details beyond the core fields ---

PERSONAL_FIELDS = ["gender", "dateOfBirth"]


@pytest.mark.asyncio
async def test_personal_details_are_returned_when_requested(
    pesu, upstream, make_response, login_payload, profile_payload
):
    upstream.side_effect = [make_response(json=login_payload), make_response(json=profile_payload)]

    result = await pesu.authenticate("user", "pass", profile=True, fields=["name", *PERSONAL_FIELDS])

    assert result["profile"] == {
        "name": "JOHN DOE",
        "gender": "Male",
        # Midnight IST on 2005-01-01; read in UTC it would be 2004-12-31
        "dateOfBirth": "2005-01-01",
    }


@pytest.mark.asyncio
async def test_the_date_of_birth_comes_from_student_photo_then_the_login(
    pesu, upstream, make_response, login_payload, profile_payload
):
    profile_payload["STUDENT_INFO"]["DateOfBirth"] = None
    profile_payload["STUDENT_PHOTO"]["dateOfBirth"] = 1104604200000  # 2005-01-02 IST
    upstream.side_effect = [make_response(json=login_payload), make_response(json=profile_payload)]
    from_photo = await pesu.authenticate("user", "pass", profile=True, fields=["dateOfBirth"])

    profile_payload["STUDENT_PHOTO"]["dateOfBirth"] = None
    upstream.side_effect = [make_response(json=login_payload), make_response(json=profile_payload)]
    from_login = await pesu.authenticate("user", "pass", profile=True, fields=["dateOfBirth"])

    assert from_photo["profile"] == {"dateOfBirth": "2005-01-02"}
    assert from_login["profile"] == {"dateOfBirth": "2005-01-01"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("timestamp", "login_value"),
    [
        (None, "01-01-2005"),  # the login's string in another format is not trusted
        (None, None),
        (10**18, None),  # out of range for a date
    ],
)
async def test_an_unusable_date_of_birth_is_null(
    pesu, upstream, make_response, login_payload, profile_payload, timestamp, login_value
):
    profile_payload["STUDENT_INFO"]["DateOfBirth"] = timestamp
    profile_payload["STUDENT_PHOTO"]["dateOfBirth"] = timestamp
    login_payload["mobileJsonObject"]["dateofBirth"] = login_value
    upstream.side_effect = [make_response(json=login_payload), make_response(json=profile_payload)]

    result = await pesu.authenticate("user", "pass", profile=True, fields=["dateOfBirth"])

    assert result["profile"] == {"dateOfBirth": None}


@pytest.mark.asyncio
async def test_a_date_of_birth_before_1970(pesu, upstream, make_response, login_payload, profile_payload):
    profile_payload["STUDENT_INFO"]["DateOfBirth"] = -19800000  # midnight IST on 1970-01-01
    upstream.side_effect = [make_response(json=login_payload), make_response(json=profile_payload)]

    result = await pesu.authenticate("user", "pass", profile=True, fields=["dateOfBirth"])

    assert result["profile"] == {"dateOfBirth": "1970-01-01"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("semesters", "roll_number"),
    [
        ([], None),
        (None, None),
        # An earlier semester's roll number is not the current one
        ([{"studentRollNo": None, "batchClassOrder": 2}, {"studentRollNo": 5, "batchClassOrder": 1}], None),
        ([{"studentRollNo": 8, "batchClassOrder": None}, {"studentRollNo": 5, "batchClassOrder": 1}], 5),
        ([{"studentRollNo": "14", "batchClassOrder": "3"}], 14),
    ],
    ids=["no semesters", "null semesters", "latest has no roll", "unordered entry", "numbers as text"],
)
async def test_the_roll_number_is_from_the_latest_semester(
    pesu, upstream, make_response, login_payload, profile_payload, semesters, roll_number
):
    profile_payload["STUDENT_SEMESTERS"] = semesters
    upstream.side_effect = [make_response(json=login_payload), make_response(json=profile_payload)]

    result = await pesu.authenticate("user", "pass", profile=True, fields=["rollNumber"])

    assert result["profile"] == {"rollNumber": roll_number}


@pytest.mark.asyncio
async def test_the_first_name_falls_back_to_student_photo_then_the_login(
    pesu, upstream, make_response, login_payload, profile_payload
):
    profile_payload["STUDENT_INFO"]["FirstName"] = None
    profile_payload["STUDENT_PHOTO"]["firstName"] = "JOHNNY"
    upstream.side_effect = [make_response(json=login_payload), make_response(json=profile_payload)]
    from_photo = await pesu.authenticate("user", "pass", profile=True, fields=["firstName"])

    profile_payload["STUDENT_PHOTO"]["firstName"] = None
    login_payload["mobileJsonObject"]["name"] = "JON"
    upstream.side_effect = [make_response(json=login_payload), make_response(json=profile_payload)]
    from_login = await pesu.authenticate("user", "pass", profile=True, fields=["firstName"])

    assert from_photo["profile"] == {"firstName": "JOHNNY"}
    assert from_login["profile"] == {"firstName": "JON"}


@pytest.mark.asyncio
async def test_the_branch_code_is_not_taken_from_the_login(
    pesu, upstream, make_response, login_payload, profile_payload
):
    """The login's "Branch:CSE" is not parsed: without BranchAbbreviation the code is null."""
    profile_payload["STUDENT_INFO"]["BranchAbbreviation"] = None
    login_payload["mobileJsonObject"]["branch"] = "Branch:ECE"
    upstream.side_effect = [make_response(json=login_payload), make_response(json=profile_payload)]

    result = await pesu.authenticate("user", "pass", profile=True, fields=["branchShortCode"])

    assert result["profile"] == {"branchShortCode": None}


@pytest.mark.asyncio
async def test_without_student_photo_there_is_no_institute_or_gender(
    pesu, upstream, make_response, login_payload, profile_payload
):
    del profile_payload["STUDENT_PHOTO"]
    upstream.side_effect = [make_response(json=login_payload), make_response(json=profile_payload)]

    result = await pesu.authenticate("user", "pass", profile=True, fields=["institute", "gender", "dateOfBirth"])

    # The date of birth is in STUDENT_INFO too
    assert result["profile"] == {"institute": None, "gender": None, "dateOfBirth": "2005-01-01"}


def test_the_default_fields_are_every_field():
    from typing import get_args

    from app.pesu import ProfileField

    assert PESUAcademy.DEFAULT_FIELDS == list(get_args(ProfileField))


# --- Telling the PRN and the SRN apart ---
#
# PRN: PES + campus digit + year of joining + 5 digits (PES1201800001).
# SRN: PES + campus digit + program + 2-digit year + branch + 3 digits (PES2UG25CS001). Students who
# joined before SRNs existed have an SRN that is their PRN.


@pytest.mark.parametrize(
    ("login_id", "expected"),
    [
        ("PES2UG25CS001", "PES2UG25CS001"),
        ("PES1PG24EC123", "PES1PG24EC123"),
        ("PES1201800001", None),  # a PRN
        ("PES2UG25CSE001", None),  # a three-letter branch
        ("PES2UG25CS01", None),  # two-digit number
        ("PES2UG2025CS001", None),  # four-digit year
        ("pes2ug25cs001", None),  # not how PESU writes it
        ("john.doe@example.com", None),
        (None, None),
    ],
)
def test_only_a_new_style_srn_is_an_srn(login_id, expected):
    assert _as_srn(login_id) == expected


@pytest.mark.asyncio
async def test_the_prn_is_found_in_any_block(pesu, upstream, make_response, login_payload, profile_payload):
    """Merging the blocks first used to keep STUDENT_INFO's loginId and drop STUDENT_PHOTO's PRN."""
    del login_payload["mobileJsonObject"]["loginId"]
    profile_payload["STUDENT_INFO"]["LoginId"] = "PES2UG25CS001"
    profile_payload["STUDENT_PHOTO"]["loginId"] = "PES2202500001"

    profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    assert (profile["prn"], profile["srn"]) == ("PES2202500001", "PES2UG25CS001")


@pytest.mark.asyncio
async def test_an_older_students_srn_is_also_their_prn(pesu, upstream, make_response, login_payload, profile_payload):
    """With no loginId anywhere, a PRN-shaped SRN still identifies the PRN, because it is the PRN."""
    del login_payload["mobileJsonObject"]["loginId"]
    del profile_payload["STUDENT_PHOTO"]
    del profile_payload["USER_ROLE"]
    profile_payload["STUDENT_INFO"].update(LoginId=None, SRN="PES1201800001")

    profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    assert profile["prn"] == profile["srn"] == "PES1201800001"


@pytest.mark.asyncio
async def test_the_srn_falls_back_to_a_new_style_srn_in_the_login(
    pesu, upstream, make_response, login_payload, profile_payload
):
    del profile_payload["STUDENT_PHOTO"]
    profile_payload["STUDENT_INFO"].update(SRN=None, LoginId="PES2202500001")
    login_payload["mobileJsonObject"]["loginId"] = "PES2UG25CS001"

    profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    assert (profile["prn"], profile["srn"]) == ("PES2202500001", "PES2UG25CS001")


@pytest.mark.asyncio
async def test_a_new_style_srn_beats_a_prn_shaped_photo_login_id(
    pesu, upstream, make_response, login_payload, profile_payload
):
    """A PRN-shaped STUDENT_PHOTO loginId is only taken as the SRN when no new-style SRN exists."""
    profile_payload["STUDENT_INFO"].update(SRN=None, LoginId="PES2UG25CS001")
    profile_payload["STUDENT_PHOTO"]["loginId"] = "PES2202500001"

    profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    assert (profile["prn"], profile["srn"]) == ("PES2202500001", "PES2UG25CS001")


@pytest.mark.asyncio
async def test_a_photo_login_id_that_is_not_an_id_is_ignored(
    pesu, upstream, make_response, login_payload, profile_payload
):
    profile_payload["STUDENT_INFO"].update(SRN=None, LoginId=None)
    profile_payload["STUDENT_PHOTO"]["loginId"] = "john.doe@example.com"

    profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    assert profile["srn"] is None
    # The login's PRN still gives the campus
    assert (profile["prn"], profile["campus"]) == ("PES2202500001", "EC")


@pytest.mark.asyncio
async def test_the_labelled_srn_is_trusted_as_sent(pesu, upstream, make_response, login_payload, profile_payload):
    """STUDENT_INFO.SRN is the one field PESU labels as the SRN, so an unfamiliar shape is not discarded."""
    profile_payload["STUDENT_INFO"]["SRN"] = "PES2UG25CSE001"

    profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    assert (profile["srn"], profile["campusCode"]) == ("PES2UG25CSE001", 2)


@pytest.mark.asyncio
async def test_the_prn_is_found_in_user_role(pesu, upstream, make_response, login_payload, profile_payload):
    """USER_ROLE's LoginId has been seen to hold the PRN, so it is used when the others do not."""
    del login_payload["mobileJsonObject"]["loginId"]
    profile_payload["STUDENT_INFO"]["LoginId"] = None

    profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    assert (profile["prn"], profile["srn"]) == ("PES2202500001", "PES2UG25CS001")


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [None, {}, {"LoginId": "NA"}, {"LoginId": 12345}])
async def test_an_empty_or_odd_user_role_is_harmless(pesu, upstream, make_response, login_payload, profile_payload, role):
    profile_payload["USER_ROLE"] = role

    profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    assert (profile["prn"], profile["srn"]) == ("PES2202500001", "PES2UG25CS001")


# --- Secondary fields fail soft ---


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("block", "key", "value", "affected"),
    [
        # PESU's style for an empty block, which a list field would otherwise reject
        ("STUDENT_SEMESTERS", None, {}, {"rollNumber": None}),
        ("USER_ROLE", None, [], {}),
        ("STUDENT_INFO", "DateOfBirth", "2005-01-01", {}),  # STUDENT_PHOTO still has the timestamp
        ("STUDENT_INFO", "FirstName", {"unexpected": True}, {}),  # STUDENT_PHOTO still has the first name
        ("STUDENT_INFO", "MiddleName", ["x"], {}),
        ("STUDENT_INFO", "LastName", {"x": 1}, {"lastName": None}),
        ("STUDENT_INFO", "BranchAbbreviation", [], {"branchShortCode": None}),
        ("STUDENT_PHOTO", "instituteName", {"x": 1}, {"institute": None}),
        ("STUDENT_PHOTO", "gender", ["Male"], {"gender": None}),
    ],
)
async def test_a_secondary_field_of_an_unexpected_shape_is_dropped(
    pesu, upstream, make_response, login_payload, profile_payload, caplog, block, key, value, affected
):
    """Only that field is lost; the rest of the profile still comes back."""
    if key is None:
        profile_payload[block] = value
    else:
        profile_payload[block][key] = value

    with caplog.at_level("WARNING"):
        profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    assert profile == {**FULL_PROFILE, **affected}
    # The field is named in the log, but never its value
    assert "Ignored an unexpected value" in caplog.text
    assert "unexpected': True" not in caplog.text


@pytest.mark.asyncio
async def test_a_login_date_of_birth_of_an_unexpected_shape_does_not_fail_the_login(
    pesu, upstream, make_response, login_payload, profile_payload
):
    login_payload["mobileJsonObject"]["dateofBirth"] = ["2005-01-01"]

    profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    # STUDENT_INFO's timestamp still gives the date of birth
    assert profile["dateOfBirth"] == "2005-01-01"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("index", "entry", "roll_number"),
    [
        # Not a semester at all: skipped, and the latest (Sem-4) is untouched
        (0, "garbage", 27),
        # The latest, with no usable roll number: there is no current one
        (1, {"studentRollNo": "27A", "batchClassOrder": 2027010199}, None),
        # The latest, with no usable order: it cannot be placed in time, so Sem-3 is the latest left
        (1, {"studentRollNo": 27, "batchClassOrder": "soon"}, 12),
    ],
)
async def test_a_malformed_semester_costs_only_itself(
    pesu, upstream, make_response, login_payload, profile_payload, index, entry, roll_number
):
    """The fixture's semesters are Sem-3 (12), Sem-4 (27, the latest) and Sem-2 (9)."""
    profile_payload["STUDENT_SEMESTERS"][index] = entry

    profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    assert profile["rollNumber"] == roll_number
    assert profile["srn"] == "PES2UG25CS001"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("block", "key", "value"),
    [
        ("STUDENT_INFO", "SRN", {"x": 1}),
        ("STUDENT_INFO", "NameAsInSSLC", ["JOHN"]),
        ("STUDENT_INFO", "Branch", {"x": 1}),
        ("STUDENT_PHOTO", "email", ["a@b.c"]),
    ],
)
async def test_a_core_field_of_an_unexpected_shape_is_still_a_parse_error(
    pesu, upstream, make_response, login_payload, profile_payload, block, key, value
):
    """A change to a field a profile cannot do without is PESU's API changing, so it stays a 422."""
    profile_payload[block][key] = value
    upstream.side_effect = [make_response(json=login_payload), make_response(json=profile_payload)]

    with pytest.raises(ProfileParseError):
        await pesu.authenticate("user", "pass", profile=True)


@pytest.mark.asyncio
async def test_blood_group_is_never_returned(pesu, upstream, make_response, login_payload, profile_payload):
    """PESU sends a blood group; it is not authentication data, so it is not read at all."""
    profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    assert "bloodGroup" not in profile
    assert "BLOODGROUPSECRET" not in str(profile)


ORIGINAL_FIELDS = ["name", "prn", "srn", "program", "branch", "semester", "section", "email", "phone", "campusCode", "campus"]


def test_the_live_tests_request_every_new_field(new_profile_fields):
    """The live specific-fields tests ask for every field added since the web flow.

    A field added later without being added to that list would otherwise never be checked against
    a real account by those tests.
    """
    assert sorted(new_profile_fields) == sorted(set(PESUAcademy.DEFAULT_FIELDS) - set(ORIGINAL_FIELDS))
    assert [field for field in PESUAcademy.DEFAULT_FIELDS if field in ORIGINAL_FIELDS] == ORIGINAL_FIELDS
