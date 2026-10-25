"""Model representing response from health endpoint."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class HealthModel(BaseModel):
    """Model representing response from health endpoint."""

    model_config = ConfigDict(strict=True, alias_generator=to_camel, populate_by_name=True)

    status: bool = Field(
        ...,
        title="Health status",
        description="indicates whether the service is alive",
        json_schema_extra={"example": True},
    )

    message: str = Field(
        ...,
        title="Health message",
        description="A string indicating the service's health",
        json_schema_extra={"example": "ok"},
    )

    timestamp: datetime = Field(
        ...,
        # Relaxed from the model-wide strict=True for this field alone. The API builds this model
        # from a datetime but serializes an ISO string onto the wire, so a strict model could not
        # parse its own responses -- which made the published schema unusable to a client wanting
        # to validate with it, and forced the documentation tests into JSON mode to compensate.
        strict=False,
        title="timestamp",
        description="returns the timestamp of when /health was used",
        json_schema_extra={"example": "2024-07-28T22:30:10.103368+05:30"},
    )

    version: str = Field(
        ...,
        title="version",
        description="The version of pesu-auth that is running",
        json_schema_extra={"example": "5.0.0"},
    )

    environment: Literal["development", "staging", "production"] = Field(
        default="development",
        title="environment",
        description="an environment variable",
        json_schema_extra={"example": "developement"},
    )
