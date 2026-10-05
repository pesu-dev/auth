"""Shared fixtures for unit tests that drive PESUAcademy against a mocked mobile API."""

import copy
from unittest.mock import AsyncMock, patch

import httpx2
import pytest

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
        "className": "Sem-4, Section C",
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
        {"studentId": "00000000-0000-0000-0000-000000000000", "studentRollNo": 12, "className": "Sem-3", "batchClassOrder": 2026071499},
        {"studentId": "00000000-0000-0000-0000-000000000000", "studentRollNo": 27, "className": "Sem-4", "batchClassOrder": 2027010199},
        {"studentId": "00000000-0000-0000-0000-000000000000", "studentRollNo": 9, "className": "Sem-2", "batchClassOrder": 2026010199},
    ],
    "STUDENT_CGPA_DETAILS": [{"USN": "PES2UG25CS001", "CGPA": "CGPASECRET"}],
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
