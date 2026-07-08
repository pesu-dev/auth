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
    mock_login = MagicMock()
    mock_login.status_code = 200
    mock_login.json.return_value = {
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

    mock_sems = MagicMock()
    mock_sems.status_code = 200
    mock_sems.json.return_value = [
        {
            "BatchClassId": 123,
            "ClassBatchSectionId": 456,
            "ClassName": "B.Tech-CSE-Sem_4"
        }
    ]

    mock_marks = MagicMock()
    mock_marks.status_code = 200
    mock_marks.json.return_value = {
        "marks_list": [
            {
                "NameAsInSSLC": "John Doe FullName",
                "subjectId": 99,
                "subjectCode": "CS101",
                "subjectName": "Computer Science"
            }
        ]
    }

    mock_post.side_effect = [mock_login, mock_sems, mock_marks]

    result = await pesu.authenticate("user", "pass", profile=True, know_your_class_and_section=True)

    assert result["status"] is True
    assert result["message"] == "Login successful."
    assert "profile" in result
    assert result["profile"]["name"] == "John Doe FullName"
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
async def test_authenticate_sslc_name_errors(mock_post, pesu):
    mock_login = MagicMock()
    mock_login.status_code = 200
    mock_login.json.return_value = {
        "login": "SUCCESS",
        "userId": "12345",
        "loginId": "PES1201800001",
        "name": "John Doe",
    }

    # 1. Test when semester endpoint fails with non-200
    mock_sems_fail = MagicMock()
    mock_sems_fail.status_code = 500

    mock_post.side_effect = [mock_login, mock_sems_fail]
    result = await pesu.authenticate("user", "pass", profile=True)
    assert result["profile"]["name"] == "John Doe"

    # 2. Test when semester endpoint returns nested JSON string and marks fail
    mock_sems_str = MagicMock()
    mock_sems_str.status_code = 200
    mock_sems_str.json.return_value = '[{"BatchClassId": 123, "ClassBatchSectionId": 456}]'

    mock_marks_fail = MagicMock()
    mock_marks_fail.status_code = 500

    mock_post.side_effect = [mock_login, mock_sems_str, mock_marks_fail]
    result = await pesu.authenticate("user", "pass", profile=True)
    assert result["profile"]["name"] == "John Doe"

    # 3. Test when marks endpoint returns nested JSON string
    mock_sems_valid = MagicMock()
    mock_sems_valid.status_code = 200
    mock_sems_valid.json.return_value = [
        {
            "BatchClassId": 123,
            "ClassBatchSectionId": 456
        }
    ]

    mock_marks_str = MagicMock()
    mock_marks_str.status_code = 200
    mock_marks_str.json.return_value = '{"marks_list": [{"NameAsInSSLC": "Nested String Name"}]}'

    mock_post.side_effect = [mock_login, mock_sems_valid, mock_marks_str]
    result = await pesu.authenticate("user", "pass", profile=True)
    assert result["profile"]["name"] == "Nested String Name"



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


def test_get_semester_from_class_branches():
    from app.pesu import _get_semester_from_class
    assert _get_semester_from_class("4th Sem", None) == "Sem-4"
    assert _get_semester_from_class("B.Tech CSE 2", None) == "Sem-2"
    assert _get_semester_from_class(None, None) is None
    assert _get_semester_from_class("NoSemesterHere", "") is None


def test_parse_sslc_name_non_dict(pesu):
    assert pesu._parse_sslc_name(None) is None
    assert pesu._parse_sslc_name([]) is None
    assert pesu._parse_sslc_name({"marks": "invalid"}) is None
    assert pesu._parse_sslc_name({"marks": [None]}) is None


@pytest.mark.asyncio
@patch("app.pesu.httpx.AsyncClient.post")
async def test_authenticate_invalid_json_responses(mock_post, pesu):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.side_effect = ValueError("Invalid JSON")
    mock_post.return_value = mock_response

    with pytest.raises(AuthenticationError) as exc_info:
        await pesu.authenticate("user", "pass")
    assert "Invalid JSON response" in str(exc_info.value)
