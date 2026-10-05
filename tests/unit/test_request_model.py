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
    model = RequestModel(username="testuser", password="testpass", fields=["name", "email", "rollNumber", "dateOfBirth"])
    assert model.fields == ["name", "email", "rollNumber", "dateOfBirth"]


def test_validate_every_profile_field_is_accepted():
    from typing import get_args

    from app.pesu import ProfileField

    every_field = list(get_args(ProfileField))
    assert RequestModel(username="testuser", password="testpass", fields=every_field).fields == every_field
    for field in every_field:
        assert RequestModel(username="testuser", password="testpass", fields=[field]).fields == [field]


def test_validate_fields_none():
    model = RequestModel(username="testuser", password="testpass", fields=None)
    assert model.fields is None


def test_validate_username_strips_whitespace():
    model = RequestModel(username="  testuser  ", password="testpass")
    assert model.username == "testuser"


def test_validate_password_strips_whitespace():
    model = RequestModel(username="testuser", password="  testpass  ")
    assert model.password == "testpass"


def test_validate_deprecated_know_your_class_and_section_key_rejected():
    """Test that the old snake_case know_your_class_and_section key is rejected as an extra field."""
    with pytest.raises(ValidationError) as exc_info:
        RequestModel.model_validate(
            {
                "username": "testuser",
                "password": "testpass",
                "know_your_class_and_section": True,
            }
        )
    errors = exc_info.value.errors()
    assert any(e["type"] == "extra_forbidden" for e in errors)
    assert "Extra inputs are not permitted" in str(exc_info.value)


def test_validate_deprecated_know_your_class_and_section_camel_key_rejected():
    """Test that the deprecated knowYourClassAndSection key is rejected as an extra field."""
    with pytest.raises(ValidationError) as exc_info:
        RequestModel.model_validate(
            {
                "username": "testuser",
                "password": "testpass",
                "knowYourClassAndSection": True,
            }
        )
    errors = exc_info.value.errors()
    assert any(e["type"] == "extra_forbidden" for e in errors)
    assert "Extra inputs are not permitted" in str(exc_info.value)


def test_validate_unknown_extra_key_rejected():
    """Test that any unknown key is rejected."""
    with pytest.raises(ValidationError) as exc_info:
        RequestModel.model_validate(
            {
                "username": "testuser",
                "password": "testpass",
                "someRandomField": "value",
            }
        )
    errors = exc_info.value.errors()
    assert any(e["type"] == "extra_forbidden" for e in errors)
    assert "Extra inputs are not permitted" in str(exc_info.value)


def test_validate_deprecated_campus_code_in_fields_rejected():
    """Test that the old snake_case campus_code is rejected as a fields value."""
    with pytest.raises(ValidationError) as exc_info:
        RequestModel(username="testuser", password="testpass", fields=["campus_code"])
    errors = exc_info.value.errors()
    assert any(e["type"] == "literal_error" for e in errors)
    assert "fields.0" in str(exc_info.value)


@pytest.mark.parametrize(
    "field",
    ["first_name", "middle_name", "last_name", "branch_short_code", "roll_number", "date_of_birth"],
)
def test_validate_snake_case_new_fields_rejected(field):
    """Fields are camelCase on the wire, like campusCode; the snake_case form is an unknown field."""
    with pytest.raises(ValidationError) as exc_info:
        RequestModel(username="testuser", password="testpass", fields=[field])
    errors = exc_info.value.errors()
    assert any(e["type"] == "literal_error" for e in errors)
    assert "fields.0" in str(exc_info.value)


@pytest.mark.parametrize("field", ["bloodGroup", "photo", "profilePicture", "programShortCode"])
def test_validate_fields_the_api_does_not_return_rejected(field):
    """Data in PESU's response that the API deliberately does not return cannot be requested."""
    with pytest.raises(ValidationError) as exc_info:
        RequestModel(username="testuser", password="testpass", fields=[field])
    assert any(e["type"] == "literal_error" for e in exc_info.value.errors())


def test_validate_removed_kycas_fields_rejected():
    """Test that the removed "Know Your Class and Section" field names are rejected as fields values."""
    for field in ("cycle", "department", "instituteName"):
        with pytest.raises(ValidationError) as exc_info:
            RequestModel(username="testuser", password="testpass", fields=[field])
        errors = exc_info.value.errors()
        assert any(e["type"] == "literal_error" for e in errors)
        assert "fields.0" in str(exc_info.value)
