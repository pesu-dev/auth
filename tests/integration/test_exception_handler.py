from app.app import app
from fastapi.testclient import TestClient


@app.get("/error")
async def error_endpoint():
    raise Exception("Random Error")


def test_exception_handler():
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/error")

    assert response.status_code == 500
    assert response.json() == {
        "status": False,
        "message": "Internal Server Error. Please try again later.",
    }
