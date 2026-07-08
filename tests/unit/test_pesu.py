from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import httpx

from app.exceptions.authentication import AuthenticationError
from app.pesu import PESUAcademy


@pytest.fixture
def pesu():
    return PESUAcademy()
@pytest.mark.asyncio
@patch("app.pesu.httpx.AsyncClient.post")
async def test_authenticate_success(mock_post, pesu):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "login": "SUCCESS",
        "userId": "12345",
        "loginId": "PES1201800001",
        "srn": "PES1UG19CS001",
        "name": "John Doe",
        "phone": "9876543210",
        "email": "john@example.com",
        "program": "Bachelor of Technology",
        "branch": "CSE",
        "className": "B.Tech-CSE-Sem_4",
        "sectionName": "A",
        "batchClass": "B.Tech CSE - 4th Semester"
    }
    mock_post.return_value = mock_response

    result = await pesu.authenticate("user", "pass", profile=True, know_your_class_and_section=True)

    assert result["status"] is True
    assert result["message"] == "Login successful."
    assert "profile" in result
    assert result["profile"]["name"] == "John Doe"
    assert result["profile"]["prn"] == "PES1201800001"
    assert result["profile"]["semester"] == "Sem-4"
    assert result["profile"]["section"] == "A"
    assert result["profile"]["campus"] == "RR"
    assert result["profile"]["campusCode"] == 1

    assert "knowYourClassAndSection" in result
    assert result["knowYourClassAndSection"]["prn"] == "PES1201800001"
    assert result["knowYourClassAndSection"]["semester"] == "Sem-4"
    assert result["knowYourClassAndSection"]["section"] == "Section A"


@pytest.mark.asyncio
@patch("app.pesu.httpx.AsyncClient.post")
async def test_authenticate_success_no_details(mock_post, pesu):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "login": "SUCCESS",
        "userId": "12345",
    }
    mock_post.return_value = mock_response

    result = await pesu.authenticate("user", "pass", profile=False, know_your_class_and_section=False)

    assert result["status"] is True
    assert result["message"] == "Login successful."
    assert "profile" not in result
    assert "knowYourClassAndSection" not in result
@pytest.mark.asyncio
@patch("app.pesu.httpx.AsyncClient.post")
async def test_authenticate_failed_credentials(mock_post, pesu):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "login": "FAILURE",
        "errorMessage": "Invalid username or password, or user does not exist"
    }
    mock_post.return_value = mock_response

    with pytest.raises(AuthenticationError) as exc_info:
        await pesu.authenticate("user", "wrongpass")
    assert "Invalid username or password" in str(exc_info.value)


@pytest.mark.asyncio
@patch("app.pesu.httpx.AsyncClient.post")
async def test_authenticate_connection_error(mock_post, pesu):
    mock_post.side_effect = httpx.RequestError("Connection timed out")

    with pytest.raises(AuthenticationError) as exc_info:
        await pesu.authenticate("user", "pass")
    assert "Connection failed" in str(exc_info.value)


@pytest.mark.asyncio
@patch("app.pesu.httpx.AsyncClient.post")
async def test_authenticate_non_200_status(mock_post, pesu):
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_post.return_value = mock_response

    with pytest.raises(AuthenticationError) as exc_info:
        await pesu.authenticate("user", "pass")
    assert "Server returned status code 500" in str(exc_info.value)


@pytest.mark.asyncio
@patch("app.pesu.httpx.AsyncClient.post")
async def test_authenticate_field_filtering(mock_post, pesu):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "login": "SUCCESS",
        "userId": "12345",
        "loginId": "PES1201800001",
        "srn": "PES1UG19CS001",
        "name": "John Doe",
        "phone": "9876543210",
        "email": "john@example.com",
        "program": "Bachelor of Technology",
        "branch": "CSE",
        "className": "B.Tech-CSE-Sem_4",
        "sectionName": "A",
        "batchClass": "B.Tech CSE - 4th Semester"
    }
    mock_post.return_value = mock_response

    result = await pesu.authenticate(
        "user", "pass", profile=True, know_your_class_and_section=True, fields=["name", "email"]
    )

    assert result["status"] is True
    assert "profile" in result
    assert "name" in result["profile"]
    assert "email" in result["profile"]
    assert "prn" not in result["profile"]
