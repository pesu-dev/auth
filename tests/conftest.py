import os
import re

import pytest
from dotenv import load_dotenv

load_dotenv()

PROFILE_VARIABLES = {
    "name": "TEST_NAME",
    "prn": "TEST_PRN",
    "srn": "TEST_SRN",
    "program": "TEST_PROGRAM",
    "branch": "TEST_BRANCH",
    "semester": "TEST_SEMESTER",
    "section": "TEST_SECTION",
    "email": "TEST_EMAIL",
    "mobile": "TEST_PHONE",
    "campusCode": "TEST_CAMPUS_CODE",
    "campus": "TEST_CAMPUS",
    "firstName": "TEST_FIRST_NAME",
    "middleName": "TEST_MIDDLE_NAME",
    "lastName": "TEST_LAST_NAME",
    "branchShortCode": "TEST_BRANCH_SHORT_CODE",
    "gender": "TEST_GENDER",
    "dateOfBirth": "TEST_DATE_OF_BIRTH",
}
# Variables hold strings; these fields are integers in the API
INTEGER_FIELDS = ("campusCode",)


@pytest.fixture
def expected_profile():
    """The test account's profile from the TEST_* variables, with None for a field that must be null.

    An empty variable stands for a field the account has no value for, which the API returns as null.
    A variable can hold only text, and GitHub Actions reads a secret that does not exist as empty, so
    such a field needs no secret at all. A variable missing from the environment is still an error.
    """
    profile = {}
    for field, variable in PROFILE_VARIABLES.items():
        value = os.getenv(variable)
        assert value is not None, f"{variable} environment variable not set"
        profile[field] = value or None
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


@pytest.fixture
def profile_variables():
    """The TEST_* variable for each profile field, in the order the API returns them."""
    return dict(PROFILE_VARIABLES)


@pytest.fixture
def specific_profile_fields():
    """Every profile field but name, in reverse order.

    A live test that asks for these checks the field filtering (name is left out) and the order of the
    response (it is the documented order, not the requested one), along with every value.
    """
    return [field for field in reversed(PROFILE_VARIABLES) if field != "name"]


@pytest.fixture
def check_live_fields(expected_profile):
    """Check that a live profile holds exactly the requested fields, each equal to its TEST_* value.

    A mismatch names the fields, never their values, so the account's data never reaches the test
    output.
    """

    def check(profile, fields):
        assert sorted(profile) == sorted(set(fields)), "the profile does not hold exactly the requested fields"
        assert list(profile) == [field for field in PROFILE_VARIABLES if field in fields], "the fields are out of order"
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
        # Either ID can be null, as any field can; check_live_fields has already compared each with its
        # TEST_* value, so a null here is one the variables expect
        srn = profile["srn"]
        ok = srn is None or prn_pattern.fullmatch(srn) is not None or srn_pattern.fullmatch(srn) is not None
        assert ok, "srn has neither the old nor the new shape"
        ok = profile["prn"] is None or srn is None or profile["prn"][3] == srn[3]
        assert ok, "prn and srn name different campuses"

    return check
