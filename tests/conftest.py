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
