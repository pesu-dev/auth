"""Model representing response from health endpoint."""

from datetime import datetime
from importlib import metadata
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

# The values PESU_AUTH_ENVIRONMENT may take; the app refuses to start with any other
Environment = Literal["development", "staging", "production"]


class HealthModel(BaseModel):
    """The body of a successful /health response. An error from /health is a ResponseModel, like every other error."""

    model_config = ConfigDict(strict=True, alias_generator=to_camel, populate_by_name=True)

    status: bool = Field(
        ...,
        title="Health Status",
        description="Indicates whether the health request was successful.",
        json_schema_extra={"example": True},
    )

    message: str = Field(
        ...,
        title="Health Message",
        description="A human-readable message providing information about the health status.",
        json_schema_extra={"example": "ok"},
    )

    timestamp: datetime = Field(
        ...,
        # Not strict: /health sends an ISO string, which a strict datetime refuses outside JSON mode, so a
        # client could not validate response.json() with this model
        strict=False,
        title="Health Check Timestamp",
        description="Time of the health check, in IST (UTC+05:30).",
        json_schema_extra={"example": "2024-07-28T22:30:10.103368+05:30"},
    )

    version: str = Field(
        ...,
        title="Version",
        description="The version of pesu-auth that is running.",
        json_schema_extra={"example": metadata.version("pesu-auth")},
    )

    environment: Environment = Field(
        ...,
        title="Environment",
        description="The deployment this instance is running as, set by `PESU_AUTH_ENVIRONMENT`.",
        json_schema_extra={"example": "development"},
    )
