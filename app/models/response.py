from pydantic import BaseModel, Field, ConfigDict
from app.models import ProfileModel
from datetime import datetime


class ResponseModel(BaseModel):
    model_config = ConfigDict(strict=True)

    status: bool = Field(
        ...,
        title="Authentication Status",
        description="Indicates whether the authentication request was successful.",
        json_schema_extra={"example": True},
    )

    message: str = Field(
        ...,
        title="Authentication Message",
        description="A human-readable message providing information about the authentication status.",
        json_schema_extra={"example": "Login successful."},
    )

    timestamp: datetime = Field(
        ...,
        title="Authentication Timestamp",
        description="Timestamp of the authentication attempt with timezone info.",
        json_schema_extra={"example": "2024-07-28T22:30:10.103368+05:30"},
    )

    profile: ProfileModel | None = Field(
        None,
        title="User Profile Data",
        description="The user's profile data returned only if authentication succeeds and profile data was requested.",
    )
