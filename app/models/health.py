"""Models representing the /health response."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class HealthChecksModel(BaseModel):
    """Internal readiness checks reported by /health.

    These checks are informational. A false value does not change ``status`` or the HTTP code.
    """

    model_config = ConfigDict(strict=True, alias_generator=to_camel, populate_by_name=True)

    csrf_cache_ready: bool = Field(
        ...,
        title="CSRF Cache Ready",
        description=(
            "Whether an unauthenticated CSRF token is cached right now. This can briefly be "
            "false after a login even when nothing is wrong: each login consumes the cached "
            "token and a replacement is fetched in the background."
        ),
        json_schema_extra={"example": True},
    )

    csrf_refresh_task_running: bool = Field(
        ...,
        title="CSRF Refresh Task Running",
        description="Whether the background CSRF token refresh task is still alive.",
        json_schema_extra={"example": True},
    )


class HealthModel(BaseModel):
    """Model representing a successful /health response."""

    model_config = ConfigDict(strict=True, alias_generator=to_camel, populate_by_name=True)

    status: bool = Field(
        ...,
        title="Health Status",
        description="Indicates whether the process is serving requests.",
        json_schema_extra={"example": True},
    )

    message: str = Field(
        ...,
        title="Health Message",
        description="A human-readable message about the health check.",
        json_schema_extra={"example": "ok"},
    )

    timestamp: datetime = Field(
        ...,
        # Same reason as ResponseModel: the wire format is an ISO string.
        strict=False,
        title="Health Timestamp",
        description="Timestamp of the health check with timezone info.",
        json_schema_extra={"example": "2024-07-28T22:30:10.103368+05:30"},
    )

    version: str = Field(
        ...,
        title="Service Version",
        description="The installed pesu-auth package version.",
        json_schema_extra={"example": "4.12.0"},
    )

    environment: Literal["development", "staging", "production"] = Field(
        ...,
        title="Deployment Environment",
        description="The environment this process was configured for via PESU_AUTH_ENVIRONMENT.",
        json_schema_extra={"example": "staging"},
    )

    checks: HealthChecksModel = Field(
        ...,
        title="Readiness Checks",
        description="Informational checks about internal process state. They do not affect status.",
    )
