"""Model representing the response after a student's authentication request."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.models import ProfileModel


class ResponseModel(BaseModel):
    """The body of every /authenticate response, and of every error this API renders.

    On success, status is true and profile is present if it was requested. On an error, status is
    false, the message says what went wrong, and there is no profile.
    """

    model_config = ConfigDict(strict=True, alias_generator=to_camel, populate_by_name=True)

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
        # Relaxed from the model-wide strict=True for this field alone. The API builds this model
        # from a datetime but serializes an ISO string onto the wire, so a strict model could not
        # parse its own responses -- which made the published schema unusable to a client wanting
        # to validate with it, and forced the documentation tests into JSON mode to compensate.
        strict=False,
        title="Authentication Timestamp",
        description="Timestamp of the authentication attempt, in IST (UTC+05:30).",
        json_schema_extra={"example": "2024-07-28T22:30:10.103368+05:30"},
    )

    profile: ProfileModel | None = Field(
        None,
        title="User Profile Data",
        description="The user's profile, present only when the login succeeded and the profile was requested.",
    )
