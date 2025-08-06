import pytest
from pydantic import ValidationError

from app.models.request import RequestModel


def test_validate_username_empty_string():
    with pytest.raises(ValidationError) as exc_info:
        RequestModel(username="", password="testpass")

    assert "Username cannot be empty" in str(exc_info.value)


def test_validate_username_whitespace_only():
    with pytest.raises(ValidationError) as exc_info:
        RequestModel(username="\t\n  \r", password="testpass")

    assert "Username cannot be empty" in str(exc_info.value)


def test_validate_username_invalid_type():
    with pytest.raises(ValidationError) as exc_info:
        RequestModel(username=123, password="testpass")

    assert exc_info.value.errors()[0]["type"] == "string_type"
    assert "Input should be a valid string" in str(exc_info.value)


def test_validate_password_empty_string():
    with pytest.raises(ValidationError) as exc_info:
        RequestModel(username="testuser", password="")

    assert "Password cannot be empty" in str(exc_info.value)


def test_validate_password_whitespace_only():
    with pytest.raises(ValidationError) as exc_info:
        RequestModel(username="testuser", password="\t\n  \r")

    assert "Password cannot be empty" in str(exc_info.value)


def test_validate_password_invalid_type():
    with pytest.raises(ValidationError) as exc_info:
        RequestModel(username="testuser", password=123)

    assert exc_info.value.errors()[0]["type"] == "string_type"
    assert "Input should be a valid string" in str(exc_info.value)


def test_validate_profile_invalid_type():
    with pytest.raises(ValidationError) as exc_info:
        RequestModel(username="testuser", password="testpass", profile=123)

    assert exc_info.value.errors()[0]["type"] == "bool_type"
    assert "Input should be a valid boolean" in str(exc_info.value)


def test_validate_fields_invalid_type():
    with pytest.raises(ValidationError) as exc_info:
        RequestModel(username="testuser", password="testpass", fields=123)

    assert exc_info.value.errors()[0]["type"] == "list_type"
    assert "Input should be a valid list" in str(exc_info.value)


def test_validate_fields_empty_list():
    with pytest.raises(ValidationError) as exc_info:
        RequestModel(username="testuser", password="testpass", fields=[])

    assert "Fields must be a non-empty list or None" in str(exc_info.value)


def test_validate_fields_invalid_field():
    with pytest.raises(ValidationError) as exc_info:
        RequestModel(username="testuser", password="testpass", fields=["invalid_field"])

    assert exc_info.value.errors()[0]["type"] == "literal_error"
    assert "fields.0" in str(exc_info.value)


def test_validate_fields_multiple_invalid_fields():
    with pytest.raises(ValidationError) as exc_info:
        RequestModel(
            username="testuser",
            password="testpass",
            fields=["invalid_field1", "invalid_field2"],
        )

    assert exc_info.value.errors()[0]["type"] == "literal_error"
    assert "fields.0" in str(exc_info.value)
    assert "fields.1" in str(exc_info.value)


def test_validate_fields_valid_fields():
    model = RequestModel(username="testuser", password="testpass", fields=["name", "email"])
    assert model.fields == ["name", "email"]


def test_validate_fields_none():
    model = RequestModel(username="testuser", password="testpass", fields=None)
    assert model.fields is None


def test_validate_username_strips_whitespace():
    model = RequestModel(username="  testuser  ", password="testpass")
    assert model.username == "testuser"


def test_validate_password_strips_whitespace():
    model = RequestModel(username="testuser", password="  testpass  ")
    assert model.password == "testpass"
