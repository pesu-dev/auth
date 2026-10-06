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
from app.pesu import _CLOSE_TASKS, DISPATCHER_URL, LOGIN_URL, PESUAcademy, _upstream_call

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
async def test_a_login_without_a_token_cannot_fetch_the_profile(
    pesu, upstream, make_response, login_payload, unusable_token
):
    _set_token(login_payload, unusable_token)
    upstream.side_effect = [make_response(json=login_payload)]

    with pytest.raises(UpstreamError):
        await pesu.authenticate("user", "pass", profile=True)

    upstream.assert_awaited_once()


@pytest.mark.asyncio
async def test_a_login_without_a_token_is_fine_without_a_profile(
    pesu, upstream, make_response, login_payload, unusable_token
):
    """Only the profile call uses the token, so a login that makes none succeeds without one."""
    _set_token(login_payload, unusable_token)
    upstream.side_effect = [make_response(json=login_payload)]

    result = await pesu.authenticate("user", "pass")

    assert result["status"] is True


def _set_token(login_payload, token):
    if token is None:
        del login_payload["accessToken"]
    else:
        login_payload["accessToken"] = token


@pytest.mark.asyncio
async def test_profile_is_built_from_both_responses(
    pesu, upstream, make_response, login_payload, profile_payload, full_profile
):
    profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    assert profile == full_profile
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
@pytest.mark.parametrize("student_info", ["unchanged", "missing", "empty"])
async def test_a_declined_profile_is_a_fetch_error(
    pesu, upstream, make_response, login_payload, profile_payload, collector, student_info
):
    """PESU declining to serve the profile is a 502 whether or not it still describes a student.

    A refusal need not carry STUDENT_INFO, and one without it is not a response we cannot read: it is
    neither a 422 nor counted as a parse error.
    """
    profile_payload["MESSAGE"] = "FAILURE_Record not found"
    if student_info == "missing":
        del profile_payload["STUDENT_INFO"]
    elif student_info == "empty":
        profile_payload["STUDENT_INFO"] = {}
    upstream.side_effect = [make_response(json=login_payload), make_response(json=profile_payload)]

    with pytest.raises(ProfileFetchError):
        await pesu.authenticate("user", "pass", profile=True)

    assert list(collector.snapshot().samples(PROFILE_PARSE_ERRORS.name)) == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "student_info",
    [
        None,
        {},
        {"UserId": None, "Unknown": "x"},
        # Not one usable value: every field null is no student at all, not a profile of nulls
        {"LoginId": {"x": 1}, "SRN": ["PES2UG25CS001"], "NameAsInSSLC": {"x": 1}},
    ],
)
async def test_a_profile_without_student_info_is_a_parse_error(
    pesu, upstream, make_response, login_payload, profile_payload, collector, caplog, student_info
):
    """STUDENT_INFO is where most of the profile comes from; nothing else stands in for it."""
    if student_info is None:
        del profile_payload["STUDENT_INFO"]
    else:
        profile_payload["STUDENT_INFO"] = student_info
    upstream.side_effect = [make_response(json=login_payload), make_response(json=profile_payload)]

    # STUDENT_PHOTO and the login response still describe the student, and are not used instead
    with caplog.at_level("WARNING"), pytest.raises(ProfileParseError):
        await pesu.authenticate("user", "pass", profile=True)

    # The log says why, though the failure has no location
    assert "STUDENT_INFO holds no student data" in caplog.text
    assert collector.snapshot().value(PROFILE_PARSE_ERRORS.name, reason="response_structure") == 1.0


@pytest.mark.asyncio
async def test_nothing_stands_in_for_a_value_student_info_lacks(
    pesu, upstream, make_response, login_payload, profile_payload
):
    """The login response and STUDENT_PHOTO carry many of the same details; none fills a gap."""
    for key in (
        "LoginId", "SRN", "NameAsInSSLC", "FirstName", "Email", "Mobile",
        "ProgramAbbreviation", "ClassName", "SectionName", "DateOfBirth",
    ):
        profile_payload["STUDENT_INFO"][key] = None
    # Every other source still has a value for each of them
    profile_payload["STUDENT_PHOTO"].update(
        loginId="PES2UG25CS001", nameAsInSSLC="JOHN DOE", email="photo@example.com", mobile="5554443332"
    )

    profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    for field in (
        "prn", "srn", "name", "firstName", "email", "mobile", "program",
        "semester", "section", "dateOfBirth",
    ):
        assert profile[field] is None, field
    # What STUDENT_INFO still has is unaffected
    assert (profile["lastName"], profile["branchShortCode"]) == ("DOE", "CSE")


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
    profile_payload["STUDENT_INFO"].update(ClassName=None, SectionName=None, ProgramAbbreviation=None, Branch=None)

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
@pytest.mark.parametrize("class_name", ["Sem-8", "Sem-4, Section C", "Minor Course (Even Sem)"])
async def test_the_semester_is_the_class_name_as_sent(
    pesu, upstream, make_response, login_payload, profile_payload, class_name
):
    """Not parsed: whatever PESU sends as STUDENT_INFO's ClassName is the semester."""
    profile_payload["STUDENT_INFO"]["ClassName"] = class_name
    login_payload["mobileJsonObject"]["className"] = "Sem-1, Section A"

    profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    assert profile["semester"] == class_name


@pytest.mark.asyncio
@pytest.mark.parametrize("class_name", ["", "   ", "NA", None])
async def test_a_blank_class_name_has_no_semester(
    pesu, upstream, make_response, login_payload, profile_payload, class_name
):
    profile_payload["STUDENT_INFO"]["ClassName"] = class_name

    profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    assert profile["semester"] is None


@pytest.mark.asyncio
async def test_na_placeholders_are_treated_as_missing(pesu, upstream, make_response, login_payload, profile_payload):
    """The web portal printed "NA" for a student with no class; it is not a semester."""
    profile_payload["STUDENT_INFO"].update(ClassName="NA", SectionName=" NA ")

    profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    assert profile["semester"] is None
    assert profile["section"] is None


@pytest.mark.asyncio
async def test_blank_values_are_treated_as_missing(pesu, upstream, make_response, login_payload, profile_payload):
    profile_payload["STUDENT_INFO"].update(Email="", Mobile="  ")

    profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    # Null rather than empty strings
    assert profile["email"] is None
    assert profile["mobile"] is None


@pytest.mark.asyncio
async def test_a_numeric_mobile_number_is_returned_as_text(
    pesu, upstream, make_response, login_payload, profile_payload
):
    profile_payload["STUDENT_INFO"]["Mobile"] = 9998887776

    profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    # A number upstream is still a string here, as the model requires
    assert profile["mobile"] == "9998887776"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("login_id", "srn"),
    [
        ("PES2202500001", "PES2UG25CS001"),  # a student whose PRN and SRN differ
        ("PES1201800001", "PES1201800001"),  # an older student, whose SRN is their PRN
        ("PES2UG25CS001", "PES2202500001"),  # swapped: still returned as PESU labels them
    ],
)
async def test_the_prn_and_srn_are_student_infos_login_id_and_srn(
    pesu, upstream, make_response, login_payload, profile_payload, login_id, srn
):
    """No format check and no other block: PESU labels these, so they are returned as labelled."""
    profile_payload["STUDENT_INFO"].update(LoginId=login_id, SRN=srn)
    # The other places PESU puts an ID hold something else, and are not used
    login_payload["mobileJsonObject"]["loginId"] = "PES9209900009"
    profile_payload["USER_ROLE"]["LoginId"] = "PES9209900009"
    profile_payload["STUDENT_PHOTO"]["loginId"] = "PES9UG99CS009"

    profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    assert (profile["prn"], profile["srn"]) == (login_id, srn)


@pytest.mark.asyncio
async def test_an_older_student_whose_prn_is_their_srn(pesu, upstream, make_response, login_payload, profile_payload):
    """Students admitted before SRNs existed have the PRN in both places."""
    profile_payload["STUDENT_INFO"].update(LoginId="PES1201800001", SRN="PES1201800001")

    profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    assert profile["prn"] == profile["srn"] == "PES1201800001"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("institute", "campus_code"),
    [("PES University (Ring Road)", 1), ("PES University (Electronic City)", 2)],
)
async def test_the_campus_is_the_institute_name_and_the_code_is_mapped_from_it(
    pesu, upstream, make_response, login_payload, profile_payload, collector, institute, campus_code
):
    profile_payload["STUDENT_PHOTO"]["instituteName"] = institute
    # Not read from the IDs: a campus digit that disagrees changes nothing
    profile_payload["STUDENT_INFO"].update(LoginId="PES9202500001", SRN="PES9UG25CS001")

    profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    assert (profile["campusCode"], profile["campus"]) == (campus_code, institute)
    assert list(collector.snapshot().samples(PROFILE_PARSE_ERRORS.name)) == []


@pytest.mark.asyncio
async def test_no_ids_means_null_ids(pesu, upstream, make_response, login_payload, profile_payload):
    profile_payload["STUDENT_INFO"].update(LoginId=None, SRN=None)

    profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    assert (profile["prn"], profile["srn"]) == (None, None)
    # The campus does not come from the IDs
    assert (profile["campusCode"], profile["campus"]) == (2, "PES University (Electronic City)")


@pytest.mark.asyncio
async def test_an_unknown_campus_name_is_returned_and_counted(
    pesu, upstream, make_response, login_payload, profile_payload, collector, caplog
):
    profile_payload["STUDENT_PHOTO"]["instituteName"] = "PES University (Hanumanthanagar)"

    with caplog.at_level("WARNING"):
        profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    # The name is still PESU's answer; only the code, which this service maps, is unknown
    assert profile["campus"] == "PES University (Hanumanthanagar)"
    assert profile["campusCode"] is None
    assert collector.snapshot().value(PROFILE_PARSE_ERRORS.name, reason="unknown_campus_code") == 1.0
    assert "Unknown campus name: PES University (Hanumanthanagar)" in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("program", ["B.Tech.", "M.Tech", "MCA", "B.Sc.(Hons)"])
async def test_the_program_is_returned_as_pesu_writes_it(
    pesu, upstream, make_response, login_payload, profile_payload, collector, program
):
    """No expansion: a full name would be our guess, and a wrong guess would be served as fact."""
    profile_payload["STUDENT_INFO"]["ProgramAbbreviation"] = program

    profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    assert profile["program"] == program
    assert list(collector.snapshot().samples(PROFILE_PARSE_ERRORS.name)) == []


@pytest.mark.asyncio
async def test_field_filtering(pesu, upstream, make_response, login_payload, profile_payload):
    upstream.side_effect = [make_response(json=login_payload), make_response(json=profile_payload)]

    fields = ["dateOfBirth", "name", "mobile", "campus", "gender", "middleName", "branchShortCode"]
    result = await pesu.authenticate("user", "pass", profile=True, fields=fields)

    assert result["profile"] == {
        "name": "JOHN DOE",
        "mobile": "9876543210",
        "campus": "PES University (Electronic City)",
        "middleName": None,
        "branchShortCode": "CSE",
        "gender": "Male",
        "dateOfBirth": "2005-01-01",
    }
    # In the documented order, whatever order they were asked for in
    assert list(result["profile"]) == [field for field in PESUAcademy.DEFAULT_FIELDS if field in fields]


@pytest.mark.asyncio
async def test_a_requested_field_upstream_does_not_have_is_none(
    pesu, upstream, make_response, login_payload, profile_payload
):
    profile_payload["STUDENT_INFO"]["ClassName"] = None
    profile_payload["STUDENT_PHOTO"]["gender"] = ""
    upstream.side_effect = [make_response(json=login_payload), make_response(json=profile_payload)]

    result = await pesu.authenticate(
        "user", "pass", profile=True, fields=["semester", "srn", "middleName", "gender", "campus"]
    )

    # Requested, so present; no value, so None
    assert result["profile"] == {
        "srn": "PES2UG25CS001",
        "semester": None,
        "campus": "PES University (Electronic City)",
        "middleName": None,
        "gender": None,
    }


def test_default_fields_are_every_profile_field(full_profile):
    assert PESUAcademy.DEFAULT_FIELDS == list(full_profile)


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
    profile_payload["STUDENT_PHOTO"] = ["FATHERNAMESECRET"]
    upstream.side_effect = [make_response(json=login_payload), make_response(json=profile_payload)]

    with caplog.at_level("DEBUG"), pytest.raises(ProfileParseError) as exc_info:
        await pesu.authenticate("user", "pass", profile=True)

    assert "STUDENT_PHOTO" in caplog.text
    for secret in secrets:
        assert secret not in caplog.text
        assert secret not in str(exc_info.value)


@pytest.mark.asyncio
async def test_parsed_login_does_not_expose_the_token_in_its_repr(login_payload):
    from app.models.upstream import LoginResponse

    login = LoginResponse.model_validate(login_payload)

    assert login.access_token == "ACCESS-TOKEN-SECRET"
    assert "ACCESS-TOKEN-SECRET" not in repr(login)
    # Fields never declared are never kept
    assert "LOGINPHOTOSECRET" not in repr(login)


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
async def test_extra_upstream_fields_are_ignored(
    pesu, upstream, make_response, login_payload, profile_payload, full_profile
):
    """PESU adding a field must not break parsing; only removing or retyping one we use can."""
    login_payload["mobileJsonObject"]["someNewField"] = {"nested": [1, 2, 3]}
    profile_payload["STUDENT_INFO"]["AnotherNewField"] = "value"
    profile_payload["BRAND_NEW_BLOCK"] = {}

    profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    assert profile == full_profile


@pytest.mark.asyncio
async def test_a_block_that_is_not_an_object_is_a_parse_error(
    pesu, upstream, make_response, login_payload, profile_payload, collector
):
    profile_payload["STUDENT_INFO"] = ["PES2UG25CS001"]
    upstream.side_effect = [make_response(json=login_payload), make_response(json=profile_payload)]

    with pytest.raises(ProfileParseError):
        await pesu.authenticate("user", "pass", profile=True)

    assert collector.snapshot().value(PROFILE_PARSE_ERRORS.name, reason="response_structure") == 1.0


@pytest.mark.asyncio
async def test_duplicate_requested_fields_are_returned_once(
    pesu, upstream, make_response, login_payload, profile_payload
):
    upstream.side_effect = [make_response(json=login_payload), make_response(json=profile_payload)]

    result = await pesu.authenticate("user", "pass", profile=True, fields=["name", "mobile", "name", "mobile"])

    assert result["profile"] == {"name": "JOHN DOE", "mobile": "9876543210"}


@pytest.mark.asyncio
async def test_fields_without_a_profile_are_ignored(pesu, login_ok):
    result = await pesu.authenticate("user", "pass", profile=False, fields=["name", "mobile", "dateOfBirth"])

    assert "profile" not in result
    login_ok.assert_awaited_once()


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


@pytest.mark.asyncio
async def test_concurrent_logins_do_not_share_anything(pesu, upstream, make_response, login_payload, profile_payload):
    """Two students logging in at once each get their own token, profile and client."""
    # token, SRN, name, first name, campus, date of birth (midnight IST)
    students = {
        "alice": ("TOKEN-ALICE", "PES1UG25CS001", "ALICE A", "ALICE", "PES University (Ring Road)", 1078425000000),
        "bob": ("TOKEN-BOB", "PES2UG25EC002", "BOB B", "BOB", "PES University (Electronic City)", 1069266600000),
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
        _, srn, name, first_name, campus, date_of_birth = students[student]
        info = {
            **profile_payload["STUDENT_INFO"],
            "SRN": srn,
            "NameAsInSSLC": name,
            "FirstName": first_name,
            "DateOfBirth": date_of_birth,
        }
        photo = {**profile_payload["STUDENT_PHOTO"], "instituteName": campus}
        return make_response(json={**profile_payload, "STUDENT_INFO": info, "STUDENT_PHOTO": photo})

    upstream.side_effect = respond

    fields = ["name", "srn", "campusCode", "campus", "firstName", "dateOfBirth"]
    alice, bob = await asyncio.gather(
        pesu.authenticate("alice", "pass", profile=True, fields=fields),
        pesu.authenticate("bob", "pass", profile=True, fields=fields),
    )

    assert alice["profile"] == {
        "name": "ALICE A",
        "srn": "PES1UG25CS001",
        "campusCode": 1,
        "campus": "PES University (Ring Road)",
        "firstName": "ALICE",
        "dateOfBirth": "2004-03-05",
    }
    assert bob["profile"] == {
        "name": "BOB B",
        "srn": "PES2UG25EC002",
        "campusCode": 2,
        "campus": "PES University (Electronic City)",
        "firstName": "BOB",
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


@pytest.mark.asyncio
@pytest.mark.parametrize("sink_contents", [[], [object()]])
async def test_an_upstream_call_without_a_status_records_no_status(collector, sink_contents):
    async with _upstream_call(collector, "login") as sink:
        sink.extend(sink_contents)

    snapshot = collector.snapshot()
    assert snapshot.value(UPSTREAM_REQUESTS.name, operation="login", outcome="success") == 1.0
    assert list(snapshot.samples(UPSTREAM_RESPONSES.name)) == []


@pytest.mark.asyncio
async def test_personal_details_are_returned_when_requested(
    pesu, upstream, make_response, login_payload, profile_payload
):
    upstream.side_effect = [make_response(json=login_payload), make_response(json=profile_payload)]

    result = await pesu.authenticate("user", "pass", profile=True, fields=["name", "gender", "dateOfBirth"])

    assert result["profile"] == {
        "name": "JOHN DOE",
        "gender": "Male",
        # Midnight IST on 2005-01-01; read in UTC it would be 2004-12-31
        "dateOfBirth": "2005-01-01",
    }


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
async def test_without_student_photo_there_is_no_campus_or_gender(
    pesu, upstream, make_response, login_payload, profile_payload
):
    del profile_payload["STUDENT_PHOTO"]
    upstream.side_effect = [make_response(json=login_payload), make_response(json=profile_payload)]

    result = await pesu.authenticate(
        "user", "pass", profile=True, fields=["campusCode", "campus", "gender", "dateOfBirth"]
    )

    # The date of birth is in STUDENT_INFO
    assert result["profile"] == {"campusCode": None, "campus": None, "gender": None, "dateOfBirth": "2005-01-01"}


def test_the_default_fields_are_every_field():
    from typing import get_args

    from app.models.profile import ProfileField

    assert PESUAcademy.DEFAULT_FIELDS == list(get_args(ProfileField))


@pytest.mark.asyncio
async def test_the_labelled_srn_is_trusted_as_sent(pesu, upstream, make_response, login_payload, profile_payload):
    """STUDENT_INFO.SRN is the one field PESU labels as the SRN, so an unfamiliar shape is not discarded."""
    profile_payload["STUDENT_INFO"]["SRN"] = "PES2UG25CSE001"

    profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    assert profile["srn"] == "PES2UG25CSE001"


@pytest.mark.asyncio
@pytest.mark.parametrize("block", ["USER_ROLE", "STUDENT_SEMESTERS", "STUDENT_CGPA_DETAILS", "PLACEMENT_DETAILS"])
@pytest.mark.parametrize("value", [None, {}, [], "garbage", {"LoginId": 12345}])
async def test_blocks_that_are_not_read_cannot_break_a_profile(
    pesu, upstream, make_response, login_payload, profile_payload, block, value, full_profile
):
    """Only STUDENT_INFO and STUDENT_PHOTO are read; whatever shape the rest take, the profile is the same."""
    profile_payload[block] = value

    profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    assert profile == full_profile


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("block", "key", "value", "fields"),
    [
        ("STUDENT_INFO", "LoginId", {"unexpected": True}, ["prn"]),
        ("STUDENT_INFO", "SRN", {"unexpected": True}, ["srn"]),
        ("STUDENT_INFO", "NameAsInSSLC", ["JOHN"], ["name"]),
        ("STUDENT_INFO", "ProgramAbbreviation", {"unexpected": True}, ["program"]),
        ("STUDENT_INFO", "Branch", {"unexpected": True}, ["branch"]),
        ("STUDENT_INFO", "ClassName", ["Sem-4"], ["semester"]),
        ("STUDENT_INFO", "SectionName", {"unexpected": True}, ["section"]),
        ("STUDENT_INFO", "Email", ["a@b.c"], ["email"]),
        ("STUDENT_INFO", "Mobile", {"unexpected": True}, ["mobile"]),
        ("STUDENT_PHOTO", "instituteName", {"unexpected": True}, ["campusCode", "campus"]),
        ("STUDENT_INFO", "FirstName", {"unexpected": True}, ["firstName"]),
        ("STUDENT_INFO", "MiddleName", ["x"], ["middleName"]),
        ("STUDENT_INFO", "LastName", {"unexpected": True}, ["lastName"]),
        ("STUDENT_INFO", "BranchAbbreviation", [], ["branchShortCode"]),
        ("STUDENT_PHOTO", "gender", ["Male"], ["gender"]),
        ("STUDENT_INFO", "DateOfBirth", "2005-01-01", ["dateOfBirth"]),
    ],
)
async def test_a_field_of_an_unexpected_shape_is_null(
    pesu, upstream, make_response, login_payload, profile_payload, caplog, full_profile, block, key, value, fields
):
    """Every field is treated the same: only that field is null, and the rest of the profile still comes back."""
    profile_payload[block][key] = value

    with caplog.at_level("WARNING"):
        profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    assert profile == {**full_profile, **dict.fromkeys(fields)}
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
async def test_blood_group_is_never_returned(pesu, upstream, make_response, login_payload, profile_payload):
    """PESU sends a blood group; it is not authentication data, so it is not read at all."""
    profile = await _profile_for(pesu, upstream, make_response, login_payload, profile_payload)

    assert "bloodGroup" not in profile
    assert "BLOODGROUPSECRET" not in str(profile)


def test_every_profile_field_has_a_test_variable(profile_variables):
    """Every field has a TEST_* variable, so the live tests compare each one with the test account's value."""
    assert list(profile_variables) == PESUAcademy.DEFAULT_FIELDS
