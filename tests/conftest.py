from dotenv import load_dotenv

load_dotenv()


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
