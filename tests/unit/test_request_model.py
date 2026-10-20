from idlelib.iomenu import errors

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


def test_validate_username_with_an_invisible_character(unprintable_username):
    with pytest.raises(ValidationError) as exc_info:
        RequestModel(username=unprintable_username, password="testpass")

    assert "Username can only contain visible characters" in str(exc_info.value)


def test_validate_username_with_inner_spaces_and_non_ascii():
    model = RequestModel(username="Jöhn Dœ@example.com", password="testpass")
    assert model.username == "Jöhn Dœ@example.com"


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
    model = RequestModel(username="testuser", password="testpass", profile=True, fields=["name", "email", "mobile", "dateOfBirth"])
    assert model.fields == ["name", "email", "mobile", "dateOfBirth"]


def test_validate_every_profile_field_is_accepted():
    from typing import get_args

    from app.models.profile import ProfileField

    every_field = list(get_args(ProfileField))
    assert RequestModel(username="testuser", password="testpass", profile=True, fields=every_field).fields == every_field
    for field in every_field:
        assert RequestModel(username="testuser", password="testpass", profile=True, fields=[field]).fields == [field]


def test_validate_fields_none():
    model = RequestModel(username="testuser", password="testpass", fields=None)
    assert model.fields is None


def test_validate_username_strips_whitespace():
    model = RequestModel(username="  testuser  ", password="testpass")
    assert model.username == "testuser"


def test_validate_password_preserves_surrounding_whitespace():
    model = RequestModel(username="testuser", password="  testpass  ")
    assert model.password == "  testpass  "


def test_validate_password_preserves_inner_whitespace():
    model = RequestModel(username="testuser", password="test pass")
    assert model.password == "test pass"


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


def test_username_limits(over_long_username):
    """Test that the username with max character limits are accepted and more than limit is rejected."""
    model = RequestModel(username="x" * RequestModel.MAX_USERNAME_LENGTH, password="testpass")
    assert model.username == "x" * RequestModel.MAX_USERNAME_LENGTH

    # For a username that crosses the limit
    with pytest.raises(ValidationError) as exc_info:
        RequestModel(username=over_long_username, password="testpass")
    assert "username" in str(exc_info.value)


def test_password_limits(over_long_password):
    """Test that the password with max character limits are accepted and more than limit is rejected."""
    model = RequestModel(username="testuser", password="x" * RequestModel.MAX_PASSWORD_LENGTH)
    assert model.password == "x" * RequestModel.MAX_PASSWORD_LENGTH

    # For a password that crosses the limit
    with pytest.raises(ValidationError) as exc_info:
        RequestModel(username="testuser", password=over_long_password)
    assert "password" in str(exc_info.value)


@pytest.mark.parametrize(
    "field",
    ["first_name", "middle_name", "last_name", "branch_short_code", "date_of_birth", "campus_code"],
)
def test_validate_snake_case_fields_rejected(field):
    """Fields are camelCase on the wire, like campusCode; the snake_case form is an unknown field."""
    with pytest.raises(ValidationError) as exc_info:
        RequestModel(username="testuser", password="testpass", fields=[field])
    errors = exc_info.value.errors()
    assert any(e["type"] == "literal_error" for e in errors)
    assert "fields.0" in str(exc_info.value)


@pytest.mark.parametrize("field", ["bloodGroup", "photo", "profilePicture", "programShortCode", "phone", "institute", "rollNumber"])
def test_validate_fields_the_api_does_not_return_rejected(field):
    """Neither what PESU sends but this API does not return, nor a field this API no longer returns, can be requested.

    PESU sends a blood group, a photo and a profile picture; programShortCode, phone, institute and rollNumber are
    fields this API returned before 5.0.0.
    """
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


def test_validate_profile_key_omitted():
    """Test that the profile key is omitted."""
    with pytest.raises(ValidationError) as exc_info:
        RequestModel(username="testuser", password="testpass", fields=["name", "srn"])
    assert ("Fields can only be requested when profile is True" in str(exc_info.value))


def test_validate_profile_is_set_as_false():
    """Test that the profile is set as false."""
    with pytest.raises(ValidationError) as exc_info:
        RequestModel(username="testuser", password="testpass", profile=False, fields=["name", "srn"])
    assert ("Fields can only be requested when profile is True" in str(exc_info.value))


def test_validate_duplicates_are_removed():
    """Test that the duplicates of fields are removed."""
    field_list = ["name", "email", "srn", "name", "email", "program"]
    request_model = RequestModel(username="testuser", password="testpass", profile=True, fields=field_list)
    assert request_model.fields == ["name", "email", "srn", "program"]


def test_validate_with_no_duplicates():
    """Test that a list with no duplicates comes back unchanged."""
    field_list = ["name", "email", "srn", "program"]
    request_model = RequestModel(username="testuser", password="testpass", profile=True, fields=field_list)
    assert request_model.fields == ["name", "email", "srn", "program"]


def test_validate_fields_with_profile_true_accepted():
    """Test that fields with profile=True are accepted."""
    field_list = ["name", "email", "srn", "program"]
    request_model = RequestModel(username="testuser", password="testpass", profile=True, fields=field_list)
    assert request_model.profile == True
    assert request_model.fields == ["name", "email", "srn", "program"]


def test_validate_profile_false_without_fields():
    """Test that profile=False without fields is accepted."""
    field_list = ["name", "email", "srn", "program"]
    request_model = RequestModel(username="testuser", password="testpass", profile=False, fields=None)
    assert request_model.profile == False
    assert request_model.fields == None
