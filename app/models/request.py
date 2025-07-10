from pydantic import BaseModel, field_validator, ConfigDict, Field
from typing import Optional, Literal
from app.constants import PESUAcademyConstants


class RequestModel(BaseModel):
    model_config = ConfigDict(strict=True)

    username: str = Field(
        ...,
        title="Username",
        description="User's identifier: SRN, PRN, email, or phone number.",
        example="PES1201800001",
    )
    password: str = Field(
        ...,
        title="Password",
        description="User's password for authentication.",
        example="mySecurePassword123",
    )
    profile: bool = Field(
        False,
        title="Profile Flag",
        description="Whether to fetch the user's profile information.",
        example=True,
    )
    fields: Optional[list[Literal[*PESUAcademyConstants.DEFAULT_FIELDS]]] = Field(
        None,
        title="Profile Fields",
        description=(
            "List of profile fields to fetch. If omitted, all default fields will be returned."
        ),
        example=["name", "email", "campus", "branch", "semester"],
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
    def validate_fields(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        """
        Validate that fields is either None or a non-empty list containing only allowed field names.
        """
        if v is not None:
            if not v:
                raise ValueError("Fields must be a non-empty list or None.")
            invalid = [f for f in v if f not in PESUAcademyConstants.DEFAULT_FIELDS]
            if invalid:
                raise ValueError(
                    f"Invalid fields: {', '.join(invalid)}. Valid fields are: {', '.join(PESUAcademyConstants.DEFAULT_FIELDS)}"
                )
        return v
