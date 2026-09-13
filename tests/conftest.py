import pytest
from dotenv import load_dotenv

load_dotenv()


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
