"""Model representing the student's authentication request."""

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator
from pydantic.alias_generators import to_camel

from app.models.profile import ProfileField


def _require_valid_text(value: str, label: str) -> None:
    """Reject a string that cannot be sent to PESU Academy.

    JSON can carry an unpaired surrogate (an escaped code point from U+D800 to U+DFFF), which decodes
    into a str that cannot be encoded as UTF-8. Left alone it fails while the login request is built,
    as a 500 for what is the caller's mistake.

    Args:
        value (str): The value to check.
        label (str): The field's name, for the error message. The value itself is never included.

    Raises:
        ValueError: If the value cannot be encoded as UTF-8.
    """
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError(f"{label} contains characters that are not valid text.") from None


class RequestModel(BaseModel):
    """Model representing the student's authentication request."""

    MAX_USERNAME_LENGTH: ClassVar[int] = 96  # 64 chars permissible before @ symbol, so 96 set to accommodate domains.
    MAX_PASSWORD_LENGTH: ClassVar[int] = 128  # PESU limit is unknown for passwords, so set as 128.

    model_config = ConfigDict(strict=True, alias_generator=to_camel, extra="forbid")

    username: str = Field(
        ...,
        title="Username",
        description=(
            "User's identifier for authentication. Can be SRN, PRN, email, or phone number, "
            f"up to {MAX_USERNAME_LENGTH} characters."
        ),
        json_schema_extra={"example": "PES1201800001"},
        max_length=MAX_USERNAME_LENGTH,
    )

    password: str = Field(
        ...,
        title="Password",
        description=(
            f"User's password, up to {MAX_PASSWORD_LENGTH} characters, counted exactly as typed. It is sent only to"
            " PESU Academy, and never stored or logged."
        ),
        json_schema_extra={"example": "mySecurePassword123"},
        max_length=MAX_PASSWORD_LENGTH,
    )

    profile: bool = Field(
        False,
        title="Profile Flag",
        description=(
            "Whether to also return the user's profile. Fetching it is a second call to PESU Academy, so the "
            "request takes longer."
        ),
        json_schema_extra={"example": True},
    )

    fields: list[ProfileField] | None = Field(
        None,
        title="Profile Fields",
        description=(
            "Which profile fields to return, from those listed in `ProfileModel`. Every field is returned when "
            "this is omitted. Can only be given when `profile` is true (otherwise the request is rejected with a 400); "
            "repeated names are ignored. Fields come back in `ProfileModel`'s order, whatever order they are asked for "
            "in, and a name that is not in `ProfileModel` is rejected."
        ),
        json_schema_extra={"example": ["name", "email", "campus", "branch", "semester", "firstName", "mobile"]},
    )

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate that username is valid and not empty after stripping whitespace."""
        v = v.strip()
        if not v:
            raise ValueError("Username cannot be empty.")
        # Line breaks and other control or invisible characters. No SRN, PRN, email or phone number has
        # them, and the username is logged, so one with a line break would write lines of its own into the logs.
        if not v.isprintable():
            raise ValueError("Username can only contain visible characters.")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate that password is valid and not empty after stripping whitespace."""
        if not v.strip():
            raise ValueError("Password cannot be empty.")
        return v

    @field_validator("fields", mode="after")
    @classmethod
    def validate_fields(cls, v: list[str] | None, info: ValidationInfo) -> list[str] | None:
        """Validate fields: a non-empty list, only with profile set to true, with duplicates removed."""
        if v is None:
            return v
        if not v:
            raise ValueError("Fields must be a non-empty list or None.")
        # profile is declared before fields, so it is in info.data unless it failed its own validation
        if info.data.get("profile") is False:
            raise ValueError("Fields can only be requested when profile is true.")
        return list(dict.fromkeys(v))

    @field_validator("username", "password", mode="before")
    @classmethod
    def validate_text(cls, v: object, info: ValidationInfo) -> object:
        """Reject text that cannot be encoded, before pydantic's own string checks run.

        Args:
            v (object): The raw value; anything that is not a str is left for pydantic to reject.
            info (ValidationInfo): Which field is being validated, for the error message.

        Returns:
            object: The value, unchanged.
        """
        if isinstance(v, str):
            _require_valid_text(v, info.field_name.capitalize())
        return v
