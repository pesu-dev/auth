import os
import re

import pytest
from dotenv import load_dotenv

load_dotenv()

# In a TEST_* profile variable, "NA" stands for a value the test account does not have (it has no
# current class, so no semester or section), which the API returns as null. A sentinel is needed
# because GitHub secrets cannot be empty.
ABSENT = "NA"
PROFILE_VARIABLES = {
    "name": "TEST_NAME",
    "prn": "TEST_PRN",
    "srn": "TEST_SRN",
    "program": "TEST_PROGRAM",
    "branch": "TEST_BRANCH",
    "semester": "TEST_SEMESTER",
    "section": "TEST_SECTION",
    "email": "TEST_EMAIL",
    "phone": "TEST_PHONE",
    "campusCode": "TEST_CAMPUS_CODE",
    "campus": "TEST_CAMPUS",
    "firstName": "TEST_FIRST_NAME",
    "middleName": "TEST_MIDDLE_NAME",
    "lastName": "TEST_LAST_NAME",
    "branchShortCode": "TEST_BRANCH_SHORT_CODE",
    "institute": "TEST_INSTITUTE",
    "rollNumber": "TEST_ROLL_NUMBER",
    "gender": "TEST_GENDER",
    "dateOfBirth": "TEST_DATE_OF_BIRTH",
}
# Variables hold strings; these fields are integers in the API
INTEGER_FIELDS = ("campusCode", "rollNumber")


@pytest.fixture
def expected_profile():
    """The test account's profile from the TEST_* variables, with None for a field that must be null."""
    profile = {}
    for field, variable in PROFILE_VARIABLES.items():
        value = os.getenv(variable)
        assert value is not None, f"{variable} environment variable not set"
        profile[field] = None if value == ABSENT else value
    for field in INTEGER_FIELDS:
        if profile[field] is not None:
            profile[field] = int(profile[field])
    return profile


@pytest.fixture(autouse=True)
def _metrics_token_unset(monkeypatch):
    """Keep /metrics open unless a test asks for a token.

    METRICS_TOKEN is read from the environment when app.metrics.auth is imported, and the
    load_dotenv() above runs before any test module imports the app. So a token left in a local
    .env -- or merely exported in the shell -- would make roughly thirty /metrics tests across the
    suite fail with a confusing 401 that has nothing to do with what they are testing. Pinning it
    here makes the suite independent of the ambient environment; the tests that exercise the token
    set it themselves.
    """
    monkeypatch.setattr("app.metrics.auth.METRICS_TOKEN", None)


def pytest_collection_modifyitems(config, items):
    # Force directory-based test ordering: unit > functional > integration
    priority = {
        "unit": 0,
        "functional": 1,
        "integration": 2,
    }

    def sort_key(item):
        for key, value in priority.items():
            if key in str(item.fspath):
                return value
        return 99

    items.sort(key=sort_key)


# The fields added with the mobile API, beyond the eleven the web flow returned. Every live test that
# requests particular fields asks for these too, so they are checked the same way as the originals.
NEW_PROFILE_FIELDS = [
    "firstName",
    "middleName",
    "lastName",
    "branchShortCode",
    "institute",
    "rollNumber",
    "gender",
    "dateOfBirth",
]


@pytest.fixture
def new_profile_fields():
    """The profile fields added with the mobile API."""
    return list(NEW_PROFILE_FIELDS)


@pytest.fixture
def check_live_fields(expected_profile):
    """Check that a live profile holds exactly the requested fields, each equal to its TEST_* value.

    A mismatch names the fields, never their values, so the account's data never reaches the test
    output.
    """

    def check(profile, fields):
        assert sorted(profile) == sorted(set(fields)), "the profile does not hold exactly the requested fields"
        mismatched = [field for field in fields if profile[field] != expected_profile[field]]
        assert not mismatched, f"these fields do not match their TEST_* values: {mismatched}"

    return check


@pytest.fixture
def check_live_profile(expected_profile, check_live_fields):
    """Check a full default profile from the live API against the test account.

    Every field must equal its TEST_* value (see check_live_fields), in the documented order. The
    IDs are also checked for shape, which does not depend on the variables at all.
    """
    from app.pesu import PESUAcademy

    # The service returns the IDs as PESU labels them, without checking their format; the live tests
    # do check it, so that a change to PESU's ID formats is noticed
    prn_pattern = re.compile(r"PES\d{10}")
    srn_pattern = re.compile(r"PES\d[A-Z]{2}\d{2}[A-Z]{2}\d{3}")

    def check(profile):
        assert list(profile) == PESUAcademy.DEFAULT_FIELDS
        assert list(expected_profile) == PESUAcademy.DEFAULT_FIELDS, "a profile field has no TEST_* variable"
        check_live_fields(profile, PESUAcademy.DEFAULT_FIELDS)
        # An older account's SRN is its PRN; a newer one's SRN is the new format. Either way both IDs
        # carry the same campus digit.
        ok = profile["prn"] is None or prn_pattern.fullmatch(profile["prn"]) is not None
        assert ok, "prn does not have the shape of a PRN"
        srn = profile["srn"] or ""
        ok = prn_pattern.fullmatch(srn) is not None or srn_pattern.fullmatch(srn) is not None
        assert ok, "srn has neither the old nor the new shape"
        ok = profile["prn"] is None or profile["prn"][3] == srn[3]
        assert ok, "prn and srn name different campuses"

    return check
