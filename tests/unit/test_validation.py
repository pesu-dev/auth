import pytest
from pydantic import ValidationError

from app.util import validate_input


def test_valid_input_username_prn():
    data = {
        "username": "PES1201800001",
        "password": "mypassword",
        "profile": True,
        "fields": ["name", "prn"],
    }
    validate_input(data)


def test_valid_input_username_email():
    data = {
        "username": "john.doe@gmail.com",
        "password": "mypassword",
        "profile": True,
        "fields": ["name", "prn"],
    }
    validate_input(data)


def test_valid_input_username_phone():
    data = {
        "username": "1234567890",
        "password": "mypassword",
        "profile": True,
        "fields": ["name", "prn"],
    }
    validate_input(data)


def test_valid_input_with_fields_none():
    data = {
        "username": "PES1201800001",
        "password": "mypassword",
        "profile": False,
        "fields": None,
    }
    validate_input(data)


def test_missing_username():
    data = {
        "password": "pass",
        "profile": True,
        "fields": ["name"],
    }
    with pytest.raises(ValidationError) as exc_info:
        validate_input(data)
    assert "Field required" in str(exc_info.value)


def test_non_string_username():
    data = {
        "username": 1234,
        "password": "pass",
        "profile": False,
        "fields": None,
    }
    with pytest.raises(ValidationError) as exc_info:
        validate_input(data)
    assert "Input should be a valid string" in str(exc_info.value)


def test_missing_password():
    data = {
        "username": "user",
        "profile": False,
        "fields": None,
    }
    with pytest.raises(ValidationError) as exc_info:
        validate_input(data)
    assert "Field required" in str(exc_info.value)


def test_profile_not_boolean():
    data = {
        "username": "user",
        "password": "pass",
        "profile": "invalid_bool",
        "fields": None,
    }
    with pytest.raises(ValidationError) as exc_info:
        validate_input(data)
    assert "Input should be a valid boolean" in str(exc_info.value)


def test_fields_invalid_type():
    data = {
        "username": "user",
        "password": "pass",
        "profile": False,
        "fields": {},
    }
    with pytest.raises(ValidationError) as exc_info:
        validate_input(data)
    assert "Input should be a valid list" in str(exc_info.value)


def test_fields_with_invalid_field_name():
    data = {
        "username": "user",
        "password": "pass",
        "profile": True,
        "fields": ["not_a_field"],
    }
    with pytest.raises(ValidationError) as exc_info:
        validate_input(data)
    assert "Input should be" in str(exc_info.value)
    assert "input_value='not_a_field'" in str(exc_info.value)
