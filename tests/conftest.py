import os
import pytest
from dotenv import load_dotenv

load_dotenv()


def pytest_collection_modifyitems(config, items):
    # Force directory-based test ordering: unit > functional > integration
    priority = {
        "unit": 0,
        "functional": 1,
        "integration": 2,
    }

    has_secrets = os.getenv("TEST_EMAIL") is not None and os.getenv("TEST_PASSWORD") is not None

    def sort_key(item):
        for key, value in priority.items():
            if key in str(item.fspath):
                return value
        return 99

    items.sort(key=sort_key)

    # Automatically skip secret-required tests if credentials are not configured in the environment
    if not has_secrets:
        skip_marker = pytest.mark.skip(
            reason="Integration/functional tests skipped because TEST_EMAIL or TEST_PASSWORD is not set."
        )
        for item in items:
            if "secret_required" in item.keywords:
                item.add_marker(skip_marker)
