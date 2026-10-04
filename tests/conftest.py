import os

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
}


@pytest.fixture
def expected_profile():
    """The test account's profile from the TEST_* variables, with None for a field that must be null."""
    profile = {}
    for field, variable in PROFILE_VARIABLES.items():
        value = os.getenv(variable)
        assert value is not None, f"{variable} environment variable not set"
        profile[field] = None if value == ABSENT else value
    if profile["campusCode"] is not None:
        profile["campusCode"] = int(profile["campusCode"])
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
def check_live_profile(expected_profile):
    """Check a default profile from the live API against the test account.

    The original fields must equal the TEST_* values. The newer fields have no TEST_* variable, so
    they are checked for consistency and format instead, which needs no new secrets. Checks compute a bool
    before asserting, so a failure never prints the account's values into the test output.
    """
    import re
    from datetime import date

    from app.pesu import PROGRAM_NAMES, PESUAcademy, _normalise_program

    def check(profile):
        assert list(profile) == PESUAcademy.DEFAULT_FIELDS
        assert {field: profile[field] for field in expected_profile} == expected_profile
        for field in ("firstName", "middleName", "lastName", "institute"):
            ok = profile[field] is None or (isinstance(profile[field], str) and profile[field].strip() == profile[field])
            assert ok, f"{field} is not a trimmed string or null"
        ok = profile["firstName"] is not None and profile["firstName"].casefold() in (profile["name"] or "").casefold()
        assert ok, "firstName is missing or not part of name"
        ok = profile["institute"] is not None and "PES" in profile["institute"]
        assert ok, "institute is missing or not a PES institute"
        ok = profile["rollNumber"] is None or (isinstance(profile["rollNumber"], int) and profile["rollNumber"] > 0)
        assert ok, "rollNumber is not a positive integer or null"
        # The short code must be what the full program name was expanded from
        short_code = profile["programShortCode"]
        ok = short_code is not None and PROGRAM_NAMES.get(_normalise_program(short_code)) == profile["program"]
        assert ok, "programShortCode does not expand to program"
        ok = isinstance(profile["gender"], str) and bool(profile["gender"])
        assert ok, "gender is missing"
        try:
            ok = date.fromisoformat(profile["dateOfBirth"]).year > 1900
        except (TypeError, ValueError):
            ok = False
        assert ok, "dateOfBirth is not a plausible YYYY-MM-DD date"
        ok = profile["bloodGroup"] is not None and re.fullmatch(r"(A|B|AB|O)[+-]", profile["bloodGroup"]) is not None
        assert ok, "bloodGroup is not a blood group"
        if expected_short_code := os.getenv("TEST_BRANCH_SHORT_CODE"):
            assert profile["branchShortCode"] == expected_short_code
        else:
            ok = profile["branchShortCode"] is None or re.fullmatch(r"[A-Z&()-]+", profile["branchShortCode"]) is not None
            assert ok, "branchShortCode does not look like a branch code"

    return check

