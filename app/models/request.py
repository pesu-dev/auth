from pydantic import BaseModel, field_validator, ConfigDict, Field
from app.pesu import PESUAcademy
from typing import Literal


class RequestModel(BaseModel):
    model_config = ConfigDict(strict=True)

    username: str = Field(
        ...,
        title="Username",
        description="User's identifier for authentication. Can be SRN, PRN, email, or phone number.",
        json_schema_extra={"example": "PES1201800001"},
    )

    password: str = Field(
        ...,
        title="Password",
        description="User's password for authentication.",
        json_schema_extra={"example": "mySecurePassword123"},
    )

    profile: bool = Field(
        False,
        title="Profile Flag",
        description="Whether to fetch the user's profile information.",
        json_schema_extra={"example": True},
    )

    fields: list[Literal[*PESUAcademy.DEFAULT_FIELDS]] | None = Field(
        None,
        title="Profile Fields",
        description=(
            "List of profile fields to fetch. If omitted, all default fields will be returned."
        ),
        json_schema_extra={"example": ["name", "email", "campus", "branch", "semester"]},
    )

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """
        Validate that username is not empty after stripping whitespace.
        """
        v = v.strip()
        if not v:
            raise ValueError("Username cannot be empty.")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """
        Validate that password is not empty after stripping whitespace.
        """
        v = v.strip()
        if not v:
            raise ValueError("Password cannot be empty.")
        return v

    @field_validator("fields")
    @classmethod
    def validate_fields(cls, v: list[str] | None) -> list[str] | None:
        """
        Validate that fields is either None or a non-empty list containing only allowed field names.
        """
        if v is not None and not v:
            raise ValueError("Fields must be a non-empty list or None.")
        return v
