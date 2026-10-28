"""Shared constants and fixtures for the unit tests."""

import copy
import importlib.util
import sys
from datetime import timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx2
import pytest
from schemathesis.specs.openapi.checks import (
    content_type_conformance,
    response_schema_conformance,
    status_code_conformance,
)

from app.models import HealthModel, MetricsModel, ResponseModel
from app.pesu import DISPATCHER_URL, LOGIN_URL

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_DIR = REPOSITORY_ROOT / "scripts" / "benchmark"
VERSION_CHECK_SCRIPT = REPOSITORY_ROOT / ".github" / "scripts" / "check_version_bump.py"
# The offset of every timestamp this API returns
IST_OFFSET = timedelta(hours=5, minutes=30)
# The variables scripts/run_tests.py needs before it runs the live tests
CREDENTIAL_VARIABLES = ("TEST_EMAIL", "TEST_PRN", "TEST_SRN", "TEST_MOBILE", "TEST_PASSWORD")
METRICS_TOKEN = "test-metrics-token"
# The models the OpenAPI docs refer to by name
DOCUMENTED_MODELS = {"HealthModel": HealthModel, "MetricsModel": MetricsModel, "ResponseModel": ResponseModel}
# Login responses' accessToken values that give no token: None stands for the key being absent
UNUSABLE_TOKENS = {"missing": None, "object": {"token": "x"}, "list": ["x"]}
AGENT_FRONTMATTER = '---\nname: reviewer\ndescription: Reviews diffs. Read-only.\ntools: ["read"]\n---\n'

# What every response must agree with the OpenAPI schema on, whatever its status
CONFORMANCE_CHECKS = (status_code_conformance, content_type_conformance, response_schema_conformance)
# Each way a login that asks for a profile can fail -- PESU Academy's answer to the login or the profile
# request, or our own code failing while it waits -- and the status /authenticate must answer with
AUTHENTICATION_FAILURES = {
    "wrong_credentials": (
        LOGIN_URL,
        lambda request: httpx2.Response(
            401, json={"statusCode": 401, "statusDescription": "Invalid Login Credentials"}
        ),
        401,
    ),
    "login_unavailable": (LOGIN_URL, lambda request: httpx2.Response(503), 502),
    "login_unreachable": (LOGIN_URL, lambda request: httpx2.ConnectError("refused", request=request), 502),
    "login_not_json": (LOGIN_URL, lambda request: httpx2.Response(200, content=b"<html></html>"), 502),
    "profile_unavailable": (DISPATCHER_URL, lambda request: httpx2.Response(500), 502),
    "profile_without_student": (
        DISPATCHER_URL,
        lambda request: httpx2.Response(200, json={"MESSAGE": "SUCCESS_Record found Successfully"}),
        422,
    ),
    "unhandled": (LOGIN_URL, lambda request: RuntimeError("unexpected"), 500),
}
# Usernames with a character no SRN, PRN, email or phone number has: each could break or forge a log line
UNPRINTABLE_USERNAMES = {
    "line_feed": "PES1UG20CS001\n2026-10-17 07:00:00,000 - ERROR - Login successful for user=admin",
    "carriage_return": "PES1UG20CS001\rforged",
    "null": "PES1UG20CS001\x00",
    "terminal_escape": "PES1UG20CS001\x1b[31m",
    "line_separator": "PES1UG20CS001\u2028forged",
    "zero_width_space": "PES1UG20CS\u200b001",
    "no_break_space": "PES1UG20CS\u00a0001",
}
# Request bodies FastAPI cannot read or validate, with the Content-Type they are sent as
UNREADABLE_BODIES = {
    "truncated_json": (b"{", "application/json"),
    "not_utf8": (b"\xff", "application/json"),
    "plain_text": (b"invalid", "text/plain"),
    "form": (b"username=u", "application/x-www-form-urlencoded"),
}

# Every route that takes no input, with the status a GET of it answers: the docs pages, which are not in
# the OpenAPI schema, and the two that are
PAGES = {
    "/": 200,
    "/docs": 200,
    "/docs/oauth2-redirect": 200,
    "/redoc": 200,
    "/openapi.json": 200,
    "/health": 200,
    "/readme": 308,
}

# Shaped like the real responses (key names and types taken from the live API, values invented).
# The personal fields this service must never keep or log -- photo, parents, address -- are
# included so tests can prove they are dropped. The IDs are where PESU has been seen to put them for
# a student whose PRN and SRN differ: the PRN under the login's loginId, STUDENT_INFO's LoginId and
# USER_ROLE's LoginId, the SRN under STUDENT_INFO's SRN and STUDENT_PHOTO's loginId. The profile is
# built from STUDENT_INFO; the login response's copies of the same details are only there to prove
# they are not used.
LOGIN_PAYLOAD = {
    "mobileJsonObject": {
        "userId": "00000000-0000-0000-0000-000000000000",
        "userRoleId": "3",
        "login": "SUCCESS",
        "errorMessage": None,
        "name": "JOHN",
        "photo": "data:image/png;base64,LOGINPHOTOSECRET",
        "phone": "9876543210",
        "email": "john.doe@example.com",
        "program": "B.Tech.",
        "branch": "Branch:CSE",
        "className": "Sem-4",
        "sectionName": "Section C",
        "loginId": "PES2202500001",
        "departmentId": "0",
        "usertype": "2",
        "dateofBirth": "2005-01-01",
    },
    "accessToken": "ACCESS-TOKEN-SECRET",
    "refreshToken": "REFRESH-TOKEN-SECRET",
    "status": 200,
    "accessTokenExpiryMinutes": 30,
}

PROFILE_PAYLOAD = {
    "MESSAGE": "SUCCESS_Record found Successfully",
    "image": "",
    "PLACEMENT_DETAILS": {},
    "USER_ROLE": {
        "LoginId": "PES2202500001",
        "UserId": "00000000-0000-0000-0000-000000000000",
        "UserTypeId": "2",
        "UserRoleId": "3",
    },
    "STUDENT_PHOTO": {
        "loginId": "PES2UG25CS001",
        "nameAsInSSLC": "JOHN DOE",
        "firstName": "JOHN",
        "gender": "Male",
        # Midnight IST on 2005-01-01, which is 2004-12-31 in UTC
        "dateOfBirth": 1104517800000,
        "profilePicture": "data:image/png;base64,PROFILEPHOTOSECRET",
        "instituteName": "PES University (Electronic City)",
    },
    "STUDENT_INFO": {
        "UserId": "00000000-0000-0000-0000-000000000000",
        "LoginId": "PES2202500001",
        "SRN": "PES2UG25CS001",
        "FirstName": "JOHN",
        "MiddleName": "",
        "LastName": "DOE",
        "NameAsInSSLC": "JOHN DOE",
        "DateOfBirth": 1104517800000,
        "BloodGroup": "BLOODGROUPSECRET",
        "SSLCMarksObtained": "MARKSSECRET",
        "Email": "john.doe@example.com",
        "Mobile": "9876543210",
        "FatherName": "FATHERNAMESECRET",
        "MotherMobileNo": "1112223334",
        "PermanentAddress": "ADDRESSSECRET",
        "ProgramId": 1,
        "ProgramAbbreviation": "B.Tech.",
        "BranchId": 3,
        "BranchAbbreviation": "CSE",
        "Branch": "Computer Science and Engineering",
        # The semester alone; the login response's className adds the section
        "ClassName": "Sem-4",
        "SectionName": "Section C",
    },
    # Not read: there for realism, and to prove a profile does not depend on it
    "STUDENT_SEMESTERS": [
        {
            "studentId": "00000000-0000-0000-0000-000000000000",
            "studentRollNo": 12,
            "className": "Sem-3",
            "batchClassOrder": 2026071499,
        },
        {
            "studentId": "00000000-0000-0000-0000-000000000000",
            "studentRollNo": 27,
            "className": "Sem-4",
            "batchClassOrder": 2027010199,
        },
        {
            "studentId": "00000000-0000-0000-0000-000000000000",
            "studentRollNo": 9,
            "className": "Sem-2",
            "batchClassOrder": 2026010199,
        },
    ],
    "STUDENT_CGPA_DETAILS": [{"USN": "PES2UG25CS001", "CGPA": "CGPASECRET"}],
}

# The profile PESUAcademy builds from PROFILE_PAYLOAD; LOGIN_PAYLOAD only supplies the token for the profile call
FULL_PROFILE = {
    "name": "JOHN DOE",
    "prn": "PES2202500001",
    "srn": "PES2UG25CS001",
    "program": "B.Tech.",
    "branch": "Computer Science and Engineering",
    "semester": "Sem-4",
    "section": "Section C",
    "email": "john.doe@example.com",
    "mobile": "9876543210",
    "campusCode": 2,
    "campus": "PES University (Electronic City)",
    "firstName": "JOHN",
    "middleName": None,
    "lastName": "DOE",
    "branchShortCode": "CSE",
    "gender": "Male",
    # Midnight IST on 2005-01-01; read in UTC it would be 2004-12-31
    "dateOfBirth": "2005-01-01",
}

# Values that must never appear in a log line or an exception message
SECRETS = (
    "LOGINPHOTOSECRET",
    "PROFILEPHOTOSECRET",
    "ACCESS-TOKEN-SECRET",
    "REFRESH-TOKEN-SECRET",
    "FATHERNAMESECRET",
    "ADDRESSSECRET",
    "1112223334",
    "MARKSSECRET",
    "BLOODGROUPSECRET",
    "CGPASECRET",
)


@pytest.fixture
def login_payload():
    """A successful login response body, safe to modify per test."""
    return copy.deepcopy(LOGIN_PAYLOAD)


@pytest.fixture
def profile_payload():
    """A successful profile response body, safe to modify per test."""
    return copy.deepcopy(PROFILE_PAYLOAD)


@pytest.fixture
def secrets():
    """Values from the fixture payloads that must never be logged."""
    return SECRETS


@pytest.fixture
def full_profile():
    """The profile built from the fixture payloads, safe to modify per test."""
    return copy.deepcopy(FULL_PROFILE)


@pytest.fixture
def conformance_checks():
    return list(CONFORMANCE_CHECKS)


@pytest.fixture(params=list(AUTHENTICATION_FAILURES.values()), ids=list(AUTHENTICATION_FAILURES))
def authentication_failure(request):
    """Each way PESU Academy can fail a login, as the URL, its answer and the status to expect, one per test."""
    return request.param


@pytest.fixture(params=list(PAGES.items()), ids=list(PAGES))
def page(request):
    """Each route that takes no input, with the status a GET of it answers, one per test."""
    return request.param


@pytest.fixture(params=list(UNPRINTABLE_USERNAMES.values()), ids=list(UNPRINTABLE_USERNAMES))
def unprintable_username(request):
    """Each username with a line break or another invisible character, one per test."""
    return request.param


@pytest.fixture(params=list(UNREADABLE_BODIES.values()), ids=list(UNREADABLE_BODIES))
def unreadable_body(request):
    """Each body that never gets past FastAPI's parsing or validation, with its Content-Type, one per test."""
    return request.param


@pytest.fixture
def ist_offset():
    return IST_OFFSET


@pytest.fixture(params=CREDENTIAL_VARIABLES)
def credential_variable(request):
    """Each variable scripts/run_tests.py needs before it runs the live tests, one per test."""
    return request.param


@pytest.fixture(params=list(UNUSABLE_TOKENS.values()), ids=list(UNUSABLE_TOKENS))
def unusable_token(request):
    """Each accessToken that gives no token, one per test; None means the key is absent."""
    return request.param


@pytest.fixture
def credential_variables():
    return CREDENTIAL_VARIABLES


@pytest.fixture
def metrics_token():
    return METRICS_TOKEN


@pytest.fixture
def documented_models():
    return DOCUMENTED_MODELS


@pytest.fixture
def agent_frontmatter():
    return AGENT_FRONTMATTER


@pytest.fixture
def repository_root():
    return REPOSITORY_ROOT


@pytest.fixture
def benchmark_dir():
    return BENCHMARK_DIR


def _load_script(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def version_check():
    """.github/scripts/check_version_bump.py, which is not in an importable package."""
    return _load_script(VERSION_CHECK_SCRIPT, "check_version_bump")


@pytest.fixture(scope="session")
def benchmark_scripts():
    """Load the benchmark scripts under names of their own, without putting scripts/benchmark on sys.path.

    They import their helper as a sibling (`from util import ...`), the way they run from that
    directory. So `util` is registered only while the other two load, then the previous entry, if
    any, is put back: no other test sees a module called `util` that is not its own.
    """
    helper = _load_script(BENCHMARK_DIR / "util.py", "benchmark_util")
    previous = sys.modules.get("util")
    sys.modules["util"] = helper
    try:
        return (
            helper,
            _load_script(BENCHMARK_DIR / "benchmark_requests.py", "benchmark_requests"),
            _load_script(BENCHMARK_DIR / "analyze_benchmark.py", "analyze_benchmark"),
        )
    finally:
        if previous is None:
            del sys.modules["util"]
        else:
            sys.modules["util"] = previous


@pytest.fixture
def benchmark_util(benchmark_scripts):
    return benchmark_scripts[0]


@pytest.fixture
def benchmark_requests(benchmark_scripts):
    return benchmark_scripts[1]


@pytest.fixture
def analyze_benchmark(benchmark_scripts):
    return benchmark_scripts[2]


@pytest.fixture
def make_response():
    """Build a real httpx2.Response, so parsing runs exactly as it does against PESU."""

    def _make(status=200, json=None, content=None):
        if json is not None:
            return httpx2.Response(status, json=json)
        return httpx2.Response(status, content=content or b"")

    return _make


@pytest.fixture
def upstream():
    """Patch the client's POST, the only verb the mobile API uses.

    Set `side_effect` to the responses in call order: the login, then the profile.
    """
    with patch("app.pesu.httpx2.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        yield mock_post


@pytest.fixture
def multipart_fields():
    """Decode a multipart request body into {field name: value}, each value exactly as sent."""

    def _decode(request):
        boundary = request.headers["content-type"].split("boundary=")[1].encode()
        fields = {}
        # Each part sits between a boundary line and the CRLF before the next one, so cutting exactly
        # those bytes keeps a value that itself starts or ends with a line break whole
        for part in request.content.split(b"--" + boundary)[1:-1]:
            head, _, value = part.removeprefix(b"\r\n").partition(b"\r\n\r\n")
            name = head.split(b'name="')[1].split(b'"')[0].decode()
            fields[name] = value.removesuffix(b"\r\n").decode()
        return fields

    return _decode


class Wire:
    """A stand-in for PESU Academy at the transport layer.

    Unlike `upstream`, which replaces `post()`, this lets the real client build and send each
    request -- headers, multipart encoding, redirect handling -- so tests see exactly what would go
    over the wire.
    """

    def __init__(self):
        self.requests = []
        self.client_options = []
        # URL -> callable(request) returning an httpx2.Response, or an exception to raise
        self.routes = {}

    def handler(self, request):
        request.read()
        self.requests.append(request)
        reply = self.routes[str(request.url)](request)
        if isinstance(reply, BaseException):
            raise reply
        return reply


@pytest.fixture
def wire(monkeypatch):
    """Route every client PESUAcademy creates through a recorded mock transport."""
    recorder = Wire()
    real_client = httpx2.AsyncClient

    def client_factory(**options):
        recorder.client_options.append(options)
        return real_client(transport=httpx2.MockTransport(recorder.handler), **options)

    monkeypatch.setattr("app.pesu.httpx2.AsyncClient", client_factory)
    return recorder
