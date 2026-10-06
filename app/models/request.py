"""Model representing the student's authentication request."""

from pydantic import BaseModel, ConfigDict, Field, field_validator
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

    model_config = ConfigDict(strict=True, alias_generator=to_camel, extra="forbid")

    username: str = Field(
        ...,
        title="Username",
        description="User's identifier for authentication. Can be SRN, PRN, email, or phone number.",
        json_schema_extra={"example": "PES1201800001"},
    )

    password: str = Field(
        ...,
        title="Password",
        description="User's password. It is sent only to PESU Academy, and never stored or logged.",
        json_schema_extra={"example": "mySecurePassword123"},
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
            "Which profile fields to return, from those listed in ProfileModel. Every field is returned when "
            "this is omitted. Only used when profile is true. Fields come back in ProfileModel's order, whatever "
            "order they are asked for in, and a name that is not in ProfileModel is rejected."
        ),
        json_schema_extra={"example": ["name", "email", "campus", "branch", "semester", "firstName", "mobile"]},
    )

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate that username is valid text and not empty after stripping whitespace."""
        v = v.strip()
        if not v:
            raise ValueError("Username cannot be empty.")
        _require_valid_text(v, "Username")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate that password is valid text and not empty after stripping whitespace."""
        v = v.strip()
        if not v:
            raise ValueError("Password cannot be empty.")
        _require_valid_text(v, "Password")
        return v

    @field_validator("fields")
    @classmethod
    def validate_fields(cls, v: list[str] | None) -> list[str] | None:
        """Validate that fields is either None or a non-empty list containing only allowed field names."""
        if v is not None and not v:
            raise ValueError("Fields must be a non-empty list or None.")
        return v
