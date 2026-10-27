"""Model representing response from health endpoint."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

# Allowed values for PESU_AUTH_ENVIRONMENT
environment_values = Literal["development", "staging", "production"]


class HealthModel(BaseModel):
    """Model representing response from health endpoint."""

    model_config = ConfigDict(strict=True, alias_generator=to_camel, populate_by_name=True)

    status: bool = Field(
        ...,
        title="Health status",
        description="Indicates whether the health request was successful.",
        json_schema_extra={"example": True},
    )

    message: str = Field(
        ...,
        title="Health message",
        description="A human-readable message providing information about the health status.",
        json_schema_extra={"example": "ok"},
    )

    timestamp: datetime = Field(
        ...,
        # Relaxed from the model-wide strict=True for this field alone. The API builds this model
        # from a datetime but serializes an ISO string onto the wire, so a strict model could not
        # parse its own responses -- which made the published schema unusable to a client wanting
        # to validate with it, and forced the documentation tests into JSON mode to compensate.
        strict=False,
        title="Health Check Timestamp",
        description="Time of the health check, in IST (UTC+05:30).",
        json_schema_extra={"example": "2024-07-28T22:30:10.103368+05:30"},
    )

    version: str = Field(
        ...,
        title="Version",
        description="The version of pesu-auth that is running.",
        json_schema_extra={"example": "5.8.0"},
    )

    environment: environment_values = Field(
        ...,
        title="Environment",
        description="The deployment this instance is running as, set by `PESU_AUTH_ENVIRONMENT`.",
        json_schema_extra={"example": "development"},
    )
