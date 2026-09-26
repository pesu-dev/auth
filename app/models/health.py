"""Model representing the response from the health check endpoint."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


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
