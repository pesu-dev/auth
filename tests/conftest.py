import os
from dotenv import load_dotenv
import pytest

# Clear any existing environment that might interfere
for key in ["REDIS_ENABLED", "REDIS_URL", "RATE_LIMIT_ENABLED"]:
    os.environ.pop(key, None)

# Override settings for testing BEFORE loading .env
os.environ["REDIS_ENABLED"] = "false"
os.environ["DEBUG"] = "true"
os.environ["LOG_LEVEL"] = "WARNING"  # Reduce log noise in tests
os.environ["RATE_LIMIT_ENABLED"] = "false"  # Disable rate limiting in tests

load_dotenv()


@pytest.fixture
def client():
    """Create a test client with Redis disabled."""
    # Import after environment variables are set
    from app.app import app
    from fastapi.testclient import TestClient
    return TestClient(app)


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
