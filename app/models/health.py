"""Model representing the response from the health check endpoint."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class HealthChecksModel(BaseModel):
    """Operational checks included in the health response."""

    model_config = ConfigDict(strict=True, alias_generator=to_camel, populate_by_name=True)

    csrf_cache_ready: bool = Field(
        ...,
        title="CSRF Cache Ready",
        description="Whether a cached unauthenticated CSRF client/token pair is currently available.",
        json_schema_extra={"example": True},
    )

    csrf_refresh_task_running: bool = Field(
        ...,
        title="CSRF Refresh Task Running",
        description="Whether the periodic CSRF refresh background task is active.",
        json_schema_extra={"example": True},
    )


class HealthModel(BaseModel):
    """Model representing the response from the health check endpoint."""

    model_config = ConfigDict(strict=True, alias_generator=to_camel, populate_by_name=True)

    status: bool = Field(
        ...,
        title="Health Status",
        description="Indicates whether the service is healthy.",
        json_schema_extra={"example": True},
    )

    message: str = Field(
        ...,
        title="Health Message",
        description="A human-readable health message.",
        json_schema_extra={"example": "ok"},
    )

    timestamp: datetime = Field(
        ...,
        strict=False,
        title="Health Timestamp",
        description="Timestamp of the health check with timezone info.",
        json_schema_extra={"example": "2024-07-28T22:30:10.103368+05:30"},
    )

    version: str = Field(
        ...,
        title="Application Version",
        description="Currently running pesu-auth version.",
        json_schema_extra={"example": "1.2.3"},
    )

    environment: str = Field(
        ...,
        title="Deployment Environment",
        description="Deployment environment inferred from runtime configuration.",
        json_schema_extra={"example": "staging"},
    )

    checks: HealthChecksModel = Field(
        ...,
        title="Health Checks",
        description="Internal readiness checks for background task and CSRF cache state.",
    )
