"""Models representing the metrics collected by the API."""

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.metrics.collector import (
    AUTHENTICATION_REQUESTS,
    AUTHENTICATION_RESULTS,
    ERRORS_BY_TYPE,
    FAILURES_BY_FAULT,
    HTTP_CLIENTS,
    LIFESPAN_EVENTS,
    PROCESS_START_TIME,
    PROFILE_FIELD_FILTERING,
    PROFILE_PARSE_ERRORS,
    REQUEST_LATENCY,
    REQUESTS_FAILED,
    REQUESTS_IN_FLIGHT,
    REQUESTS_SUCCESS,
    REQUESTS_TOTAL,
    RESPONSES_BY_STATUS,
    ROUTE_LATENCY,
    ROUTE_REQUESTS,
    UPSTREAM_LATENCY,
    UPSTREAM_REQUESTS,
    UPSTREAM_RESPONSES,
    VALIDATION_ERRORS,
    MetricsSnapshot,
)


def _counts(snapshot: MetricsSnapshot, name: str, label: str) -> dict[str, int]:
    """Collapse a single-label counter family into a plain mapping of label value to count.

    Args:
        snapshot (MetricsSnapshot): The snapshot to read.
        name (str): The counter family name.
        label (str): The label whose value becomes the key.

    Returns:
        dict[str, int]: The counts, keyed by label value.
    """
    return {labels[label]: int(value) for labels, value in snapshot.samples(name)}


def _upstream(snapshot: MetricsSnapshot) -> dict[str, UpstreamOperationModel]:
    """Gather the per-operation view of calls made to PESU Academy.

    Args:
        snapshot (MetricsSnapshot): The snapshot to read.

    Returns:
        dict[str, UpstreamOperationModel]: One entry per operation that has been attempted.
    """
    outcomes: dict[str, dict[str, int]] = {}
    for labels, value in snapshot.samples(UPSTREAM_REQUESTS.name):
        outcomes.setdefault(labels["operation"], {})[labels["outcome"]] = int(value)
    statuses: dict[str, dict[str, int]] = {}
    for labels, value in snapshot.samples(UPSTREAM_RESPONSES.name):
        statuses.setdefault(labels["operation"], {})[labels["status"]] = int(value)
    return {
        operation: UpstreamOperationModel(
            success=counts.get("success", 0),
            error=counts.get("error", 0),
            cancelled=counts.get("cancelled", 0),
            latency=LatencyModel.from_snapshot(snapshot, UPSTREAM_LATENCY.name, operation=operation),
            responses_by_status=statuses.get(operation, {}),
        )
        for operation, counts in outcomes.items()
    }


class LatencyModel(BaseModel):
    """Model representing aggregate request latency."""

    model_config = ConfigDict(strict=True, alias_generator=to_camel, populate_by_name=True)

    sum_seconds: float = Field(
        ...,
        title="Total Latency",
        description="Cumulative seconds spent answering requests.",
        json_schema_extra={"example": 742.1841932},
    )

    count: int = Field(
        ...,
        title="Observation Count",
        description="Number of requests whose latency was recorded.",
        json_schema_extra={"example": 1284},
    )

    average_seconds: float | None = Field(
        None,
        title="Mean Latency",
        description="Mean seconds per request, or null when nothing has been recorded yet.",
        json_schema_extra={"example": 0.5779},
    )

    @classmethod
    def from_snapshot(cls, snapshot: MetricsSnapshot, name: str, /, **labels: str) -> LatencyModel:
        """Build a latency view from a snapshot's sum and count series.

        Args:
            snapshot (MetricsSnapshot): The snapshot to read.
            name (str): The summary family name, without a suffix.
            **labels (str): The label set identifying the series.

        Returns:
            LatencyModel: The aggregated latency for that label set.
        """
        total = snapshot.value(f"{name}_sum", **labels)
        count = snapshot.value(f"{name}_count", **labels)
        return cls(
            sum_seconds=float(total),
            count=int(count),
            average_seconds=float(total / count) if count else None,
        )


class RequestCountsModel(BaseModel):
    """Model representing request outcome counts."""

    model_config = ConfigDict(strict=True, alias_generator=to_camel, populate_by_name=True)

    total: int = Field(
        ...,
        title="Total Requests",
        description="Requests received.",
        json_schema_extra={"example": 1284},
    )

    success: int = Field(
        ...,
        title="Successful Requests",
        description="Requests answered with a status below 400.",
        json_schema_extra={"example": 1102},
    )

    failed: int = Field(
        ...,
        title="Failed Requests",
        description="Requests answered with a status of 400 or above.",
        json_schema_extra={"example": 182},
    )


class AuthenticationCountsModel(BaseModel):
    """Model representing authentication request counts, split by whether profile data was requested."""

    model_config = ConfigDict(strict=True, alias_generator=to_camel, populate_by_name=True)

    total: int = Field(
        ...,
        title="Authentication Requests",
        description="Authentication requests received.",
        json_schema_extra={"example": 774},
    )

    with_profile: int = Field(
        ...,
        title="With Profile Data",
        description="Authentication requests that asked for profile data.",
        json_schema_extra={"example": 134},
    )

    without_profile: int = Field(
        ...,
        title="Without Profile Data",
        description="Authentication requests that did not ask for profile data.",
        json_schema_extra={"example": 640},
    )


class RouteMetricsModel(BaseModel):
    """Model representing the traffic served by a single route."""

    model_config = ConfigDict(strict=True, alias_generator=to_camel, populate_by_name=True)

    requests: int = Field(
        ...,
        title="Route Requests",
        description="Requests matched to this route.",
        json_schema_extra={"example": 774},
    )

    latency: LatencyModel = Field(
        ...,
        title="Route Latency",
        description="Aggregate latency for this route.",
    )


class UpstreamOperationModel(BaseModel):
    """Model representing one kind of call made to PESU Academy."""

    model_config = ConfigDict(strict=True, alias_generator=to_camel, populate_by_name=True)

    success: int = Field(
        ...,
        title="Successful Calls",
        description="Calls that returned without raising.",
        json_schema_extra={"example": 1280},
    )

    error: int = Field(
        ...,
        title="Failed Calls",
        description="Calls that raised, including timeouts and connection failures.",
        json_schema_extra={"example": 4},
    )

    cancelled: int = Field(
        ...,
        title="Cancelled Calls",
        description="Calls abandoned because the caller disconnected or the process shut down.",
        json_schema_extra={"example": 1},
    )

    latency: LatencyModel = Field(
        ...,
        title="Upstream Latency",
        description="Aggregate seconds spent waiting on this operation.",
    )

    responses_by_status: dict[str, int] = Field(
        ...,
        title="Responses by Status",
        description="Upstream response counts keyed by HTTP status code.",
        json_schema_extra={"example": {"200": 1280}},
    )


class MetricsModel(BaseModel):
    """Model representing a point-in-time view of the API's collected metrics."""

    model_config = ConfigDict(strict=True, alias_generator=to_camel, populate_by_name=True)

    start_time_seconds: float = Field(
        ...,
        title="Process Start Time",
        description="Start time of this process since the Unix epoch, in seconds. Counters reset on restart.",
        json_schema_extra={"example": 1757660400.12},
    )

    uptime_seconds: float = Field(
        ...,
        title="Uptime",
        description="Seconds since this process started collecting.",
        json_schema_extra={"example": 3612.44},
    )

    requests: RequestCountsModel = Field(
        ...,
        title="Request Counts",
        description="Request outcome counts.",
    )

    latency: LatencyModel = Field(
        ...,
        title="Request Latency",
        description="Aggregate latency across all routes.",
    )

    authentication: AuthenticationCountsModel = Field(
        ...,
        title="Authentication Counts",
        description="Authentication requests received, split by whether profile data was requested.",
    )

    responses_by_status: dict[str, int] = Field(
        ...,
        title="Responses by Status",
        description="Response counts keyed by HTTP status code.",
        json_schema_extra={"example": {"200": 1094, "401": 160, "502": 6}},
    )

    requests_by_route: dict[str, RouteMetricsModel] = Field(
        ...,
        title="Requests by Route",
        description='Per-route traffic, keyed by "METHOD route-template". Unmatched paths collapse into "<unmatched>".',
        json_schema_extra={
            "example": {
                "POST /authenticate": {
                    "requests": 774,
                    "latency": {"sumSeconds": 741.2118, "count": 774, "averageSeconds": 0.9576},
                }
            }
        },
    )

    errors_by_type: dict[str, int] = Field(
        ...,
        title="Errors by Type",
        description="Counts of errors rendered by an exception handler, keyed by exception class name.",
        json_schema_extra={"example": {"AuthenticationError": 160, "RequestValidationError": 12}},
    )

    requests_in_flight: int = Field(
        ...,
        title="Requests in Flight",
        description="Requests received but not yet answered. Explains why total can exceed success plus failed.",
        json_schema_extra={"example": 1},
    )

    failures_by_fault: dict[str, int] = Field(
        ...,
        title="Failures by Fault",
        description='Failed requests keyed by whose fault it was: "client" for 4xx, "server" for 5xx.',
        json_schema_extra={"example": {"client": 172, "server": 10}},
    )

    validation_errors_by_field: dict[str, int] = Field(
        ...,
        title="Validation Errors by Field",
        description="Request validation failures keyed by the field that failed.",
        json_schema_extra={"example": {"username": 8, "password": 4}},
    )

    authentication_results: dict[str, int] = Field(
        ...,
        title="Authentication Results",
        description=(
            'Authentication attempts keyed by outcome: "success" or "failure". Why a failure '
            "happened is in errorsByType, which names the exception class."
        ),
        json_schema_extra={"example": {"success": 612, "failure": 162}},
    )

    profile_field_filtering: dict[str, int] = Field(
        ...,
        title="Profile Field Filtering",
        description='Profile fetches keyed by whether the returned fields were narrowed: "true" or "false".',
        json_schema_extra={"example": {"true": 40, "false": 94}},
    )

    profile_parse_errors: dict[str, int] = Field(
        ...,
        title="Profile Parse Errors",
        description="Profile response parse failures keyed by what could not be parsed or mapped.",
        json_schema_extra={"example": {"unknown_program": 3}},
    )

    upstream: dict[str, UpstreamOperationModel] = Field(
        ...,
        title="Upstream Calls",
        description="Calls made to PESU Academy, keyed by operation.",
        json_schema_extra={
            "example": {
                "login": {
                    "success": 774,
                    "error": 2,
                    "latency": {"sumSeconds": 620.4, "count": 776, "averageSeconds": 0.7995},
                    "responsesByStatus": {"200": 774},
                }
            }
        },
    )

    http_clients: dict[str, int] = Field(
        ...,
        title="HTTP Clients",
        description="Upstream client lifecycle events. created minus closed is what is still open.",
        json_schema_extra={"example": {"created": 776, "closed": 776}},
    )

    lifespan_events: dict[str, int] = Field(
        ...,
        title="Lifespan Events",
        description="Application startup and shutdown events seen by this process.",
        json_schema_extra={"example": {"startup": 1}},
    )

    @classmethod
    def from_snapshot(cls, snapshot: MetricsSnapshot) -> MetricsModel:
        """Build the JSON metrics view from a collector snapshot.

        Every value is cast explicitly: the collector stores floats, and `strict=True` rejects a
        float for an int field, so an un-cast value would be a 500 rather than a payload.

        Args:
            snapshot (MetricsSnapshot): The snapshot to render.

        Returns:
            MetricsModel: The validated metrics payload.
        """
        with_profile = int(snapshot.value(AUTHENTICATION_REQUESTS.name, profile="true"))
        without_profile = int(snapshot.value(AUTHENTICATION_REQUESTS.name, profile="false"))
        return cls(
            start_time_seconds=float(snapshot.value(PROCESS_START_TIME.name)),
            uptime_seconds=float(snapshot.uptime_seconds),
            requests=RequestCountsModel(
                total=int(snapshot.value(REQUESTS_TOTAL.name)),
                success=int(snapshot.value(REQUESTS_SUCCESS.name)),
                failed=int(snapshot.value(REQUESTS_FAILED.name)),
            ),
            latency=LatencyModel.from_snapshot(snapshot, REQUEST_LATENCY.name),
            authentication=AuthenticationCountsModel(
                total=with_profile + without_profile,
                with_profile=with_profile,
                without_profile=without_profile,
            ),
            responses_by_status={
                labels["status"]: int(value) for labels, value in snapshot.samples(RESPONSES_BY_STATUS.name)
            },
            requests_by_route={
                f"{labels['method']} {labels['route']}": RouteMetricsModel(
                    requests=int(value),
                    latency=LatencyModel.from_snapshot(snapshot, ROUTE_LATENCY.name, **labels),
                )
                for labels, value in snapshot.samples(ROUTE_REQUESTS.name)
            },
            errors_by_type={labels["type"]: int(value) for labels, value in snapshot.samples(ERRORS_BY_TYPE.name)},
            requests_in_flight=int(snapshot.value(REQUESTS_IN_FLIGHT.name)),
            failures_by_fault=_counts(snapshot, FAILURES_BY_FAULT.name, "fault"),
            validation_errors_by_field=_counts(snapshot, VALIDATION_ERRORS.name, "field"),
            authentication_results=_counts(snapshot, AUTHENTICATION_RESULTS.name, "result"),
            profile_field_filtering=_counts(snapshot, PROFILE_FIELD_FILTERING.name, "enabled"),
            profile_parse_errors=_counts(snapshot, PROFILE_PARSE_ERRORS.name, "reason"),
            upstream=_upstream(snapshot),
            http_clients=_counts(snapshot, HTTP_CLIENTS.name, "event"),
            lifespan_events=_counts(snapshot, LIFESPAN_EVENTS.name, "event"),
        )
