from fastapi.testclient import TestClient

from app.app import app


def test_readme_redirects_permanently_to_the_repository():
    with TestClient(app) as client:
        response = client.get("/readme", follow_redirects=False)

    # 308, not 301: a permanent redirect that keeps the method
    assert response.status_code == 308
    assert response.headers["location"] == "https://github.com/pesu-dev/auth"
