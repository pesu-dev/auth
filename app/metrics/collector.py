"""The metric family registry and the in-memory collector behind the /metrics endpoints."""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping

# A label set, normalised to a sorted tuple of pairs so that it can key a dict
LabelKey = tuple[tuple[str, str], ...]
MetricType = Literal["counter", "gauge", "summary"]

METRIC_PREFIX = "pesu_auth_"


@dataclass(frozen=True, slots=True)
class MetricFamily:
    """A metric family: its exposed name, documentation, type and permitted label names."""

    name: str
    documentation: str
    metric_type: MetricType
    labels: tuple[str, ...] = ()


REQUESTS_TOTAL = MetricFamily(
    f"{METRIC_PREFIX}requests_total",
    "HTTP requests received.",
    "counter",
)
REQUESTS_SUCCESS = MetricFamily(
    f"{METRIC_PREFIX}requests_success_total",
    "HTTP requests answered with a status below 400.",
    "counter",
)
REQUESTS_FAILED = MetricFamily(
    f"{METRIC_PREFIX}requests_failed_total",
    "HTTP requests answered with a status of 400 or above.",
    "counter",
)
RESPONSES_BY_STATUS = MetricFamily(
    f"{METRIC_PREFIX}responses_total",
    "HTTP responses, by status code.",
    "counter",
    ("status",),
)
ROUTE_REQUESTS = MetricFamily(
    f"{METRIC_PREFIX}route_requests_total",
    "HTTP requests, by matched route and method.",
    "counter",
    ("method", "route"),
)
ERRORS_BY_TYPE = MetricFamily(
    f"{METRIC_PREFIX}errors_total",
    "Errors rendered by an exception handler, by exception class.",
    "counter",
    ("type",),
)
AUTHENTICATION_REQUESTS = MetricFamily(
    f"{METRIC_PREFIX}authentication_requests_total",
    "Authentication requests, by whether profile data was requested.",
    "counter",
    ("profile",),
)
REQUEST_LATENCY = MetricFamily(
    f"{METRIC_PREFIX}request_latency_seconds",
    "Seconds from receiving a request to starting its response.",
    "summary",
)
ROUTE_LATENCY = MetricFamily(
    f"{METRIC_PREFIX}route_latency_seconds",
    "Seconds from receiving a request to starting its response, by route.",
    "summary",
    ("method", "route"),
)
PROCESS_START_TIME = MetricFamily(
    f"{METRIC_PREFIX}process_start_time_seconds",
    "Start time of the process since the Unix epoch, in seconds.",
    "gauge",
)
REQUESTS_IN_FLIGHT = MetricFamily(
    f"{METRIC_PREFIX}requests_in_flight",
    "Requests received but not yet answered.",
    "gauge",
)
FAILURES_BY_FAULT = MetricFamily(
    f"{METRIC_PREFIX}failures_total",
    "Failed requests, by whose fault it was: the caller's (4xx) or ours (5xx).",
    "counter",
    ("fault",),
)
VALIDATION_ERRORS = MetricFamily(
    f"{METRIC_PREFIX}validation_errors_total",
    "Request validation failures, by the field that failed.",
    "counter",
    ("field",),
)
PROFILE_FIELD_FILTERING = MetricFamily(
    f"{METRIC_PREFIX}profile_field_filtering_total",
    "Profile fetches, by whether the caller narrowed the fields returned.",
    "counter",
    ("enabled",),
)
AUTHENTICATION_RESULTS = MetricFamily(
    f"{METRIC_PREFIX}authentication_results_total",
    "Authentication attempts, by outcome. errors_total says why one failed.",
    "counter",
    ("result",),
)
PROFILE_PARSE_ERRORS = MetricFamily(
    f"{METRIC_PREFIX}profile_parse_errors_total",
    "Profile page parse failures, by what could not be parsed.",
    "counter",
    ("reason",),
)
UPSTREAM_REQUESTS = MetricFamily(
    f"{METRIC_PREFIX}upstream_requests_total",
    "Requests made to PESU Academy, by operation and outcome.",
    "counter",
    ("operation", "outcome"),
)
UPSTREAM_RESPONSES = MetricFamily(
    f"{METRIC_PREFIX}upstream_responses_total",
    "Responses from PESU Academy, by operation and status code.",
    "counter",
    ("operation", "status"),
)
UPSTREAM_LATENCY = MetricFamily(
    f"{METRIC_PREFIX}upstream_latency_seconds",
    "Seconds spent waiting on PESU Academy, by operation.",
    "summary",
    ("operation",),
)
CSRF_CACHE = MetricFamily(
    f"{METRIC_PREFIX}csrf_cache_total",
    "Lookups of the cached unauthenticated CSRF client, by whether the cache was warm.",
    "counter",
    ("outcome",),
)
CSRF_REFRESHES = MetricFamily(
    f"{METRIC_PREFIX}csrf_refreshes_total",
    "Periodic background refreshes of the unauthenticated CSRF token, by outcome.",
    "counter",
    ("outcome",),
)
PREFETCH_TASKS = MetricFamily(
    f"{METRIC_PREFIX}prefetch_tasks_total",
    "Background CSRF prefetch tasks, by outcome.",
    "counter",
    ("outcome",),
)
HTTP_CLIENTS = MetricFamily(
    f"{METRIC_PREFIX}http_clients_total",
    "Upstream HTTP client lifecycle. created minus closed is how many are still open.",
    "counter",
    ("event",),
)
LIFESPAN_EVENTS = MetricFamily(
    f"{METRIC_PREFIX}lifespan_events_total",
    "Application lifespan events, by kind.",
    "counter",
    ("event",),
)

# Render order, and the single source of HELP and TYPE shared by both views
FAMILIES: tuple[MetricFamily, ...] = (
    REQUESTS_TOTAL,
    REQUESTS_SUCCESS,
    REQUESTS_FAILED,
    RESPONSES_BY_STATUS,
    ROUTE_REQUESTS,
    ERRORS_BY_TYPE,
    AUTHENTICATION_REQUESTS,
    AUTHENTICATION_RESULTS,
    PROFILE_FIELD_FILTERING,
    PROFILE_PARSE_ERRORS,
    VALIDATION_ERRORS,
    FAILURES_BY_FAULT,
    REQUEST_LATENCY,
    ROUTE_LATENCY,
    UPSTREAM_REQUESTS,
    UPSTREAM_RESPONSES,
    UPSTREAM_LATENCY,
    CSRF_CACHE,
    CSRF_REFRESHES,
    PREFETCH_TASKS,
    HTTP_CLIENTS,
    LIFESPAN_EVENTS,
    REQUESTS_IN_FLIGHT,
    PROCESS_START_TIME,
)


@dataclass(frozen=True, slots=True)
class MetricsSnapshot:
    """A point-in-time copy of every series held by a collector."""

    start_time: float
    uptime_seconds: float
    values: Mapping[str, Mapping[LabelKey, float]]

    def value(self, name: str, /, **labels: str) -> float:
        """Return a single series value, or 0.0 if it was never recorded.

        Args:
            name (str): The stored series name, including any _sum or _count suffix.
            **labels (str): The label set identifying the series.

        Returns:
            float: The recorded value, defaulting to 0.0.
        """
        return self.values.get(name, {}).get(tuple(sorted(labels.items())), 0.0)

    def samples(self, name: str) -> Iterator[tuple[dict[str, str], float]]:
        """Yield every (labels, value) pair recorded against a stored series, in label order.

        Args:
            name (str): The stored series name, including any _sum or _count suffix.

        Yields:
            tuple[dict[str, str], float]: The label set and its value.
        """
        series = self.values.get(name, {})
        for key in sorted(series):
            yield dict(key), series[key]


class MetricsCollector:
    """Process-local counters for the traffic this process has served.

    Deliberately unsynchronised. Every mutation is a dict read followed by a dict write with no
    await in between, so the event loop cannot interleave two increments -- a task runs to its next
    suspension point before any other task resumes. The asyncio.Lock in app/pesu.py exists because
    that code swaps several fields *around* an await, which is a different situation, and an
    asyncio.Lock would give no protection against threads anyway. This reasoning stops holding under
    `uvicorn --workers > 1` (which needs a shared store, not a lock) or on a free-threaded build.

    Counters live in memory and reset when the process restarts, which on Render is often. That is
    why process_start_time_seconds is exposed: a scraper needs it to tell a restart apart from a
    drop in traffic.
    """

    def __init__(self, *, clock: Callable[[], float] | None = None) -> None:
        """Initialize the collector and seed every unlabelled series at zero.

        Args:
            clock (Callable[[], float] | None): Wall-clock source, injected by tests.
        """
        self._clock = clock or time.time
        self._start_time = self._clock()
        self._values: defaultdict[str, dict[LabelKey, float]] = defaultdict(dict)
        # Seed the unlabelled series so a freshly started process still exposes them. Without this
        # there is no series at all until the first request, and a rate over a series that springs
        # into existence mid-window reads as a spike.
        for family in FAMILIES:
            if family.labels:
                continue
            if family.metric_type == "summary":
                self._values[f"{family.name}_sum"][()] = 0.0
                self._values[f"{family.name}_count"][()] = 0.0
            else:
                self._values[family.name][()] = 0.0
        self._values[PROCESS_START_TIME.name][()] = self._start_time

    @staticmethod
    def _key(family: MetricFamily, labels: Mapping[str, str]) -> LabelKey:
        """Normalise and validate a label set against its family.

        Args:
            family (MetricFamily): The family being recorded against.
            labels (Mapping[str, str]): The supplied labels.

        Returns:
            LabelKey: The labels as a sorted tuple of pairs.

        Raises:
            ValueError: If the label names do not match the family's declared labels.
        """
        if set(labels) != set(family.labels):
            raise ValueError(f"{family.name} expects labels {family.labels}, got {tuple(sorted(labels))}.")
        return tuple(sorted(labels.items()))

    def increment(self, family: MetricFamily, value: float = 1.0, /, **labels: str) -> None:
        """Add to a counter series.

        Args:
            family (MetricFamily): The counter family to record against.
            value (float): The amount to add. Defaults to 1.0. Positional-only, so a family may
                declare a label named "value" without it being captured here instead.
            **labels (str): The label set, which must match the family's declared labels.
        """
        key = self._key(family, labels)
        series = self._values[family.name]
        series[key] = series.get(key, 0.0) + value

    def observe(self, family: MetricFamily, seconds: float, /, **labels: str) -> None:
        """Record one observation against a summary family's sum and count series.

        Args:
            family (MetricFamily): The summary family to record against.
            seconds (float): The observed value.
            **labels (str): The label set, which must match the family's declared labels.
        """
        key = self._key(family, labels)
        for name, amount in ((f"{family.name}_sum", seconds), (f"{family.name}_count", 1.0)):
            series = self._values[name]
            series[key] = series.get(key, 0.0) + amount

    def snapshot(self) -> MetricsSnapshot:
        """Copy every series so a renderer can iterate without observing further mutation.

        Returns:
            MetricsSnapshot: An immutable view of the current values.
        """
        return MetricsSnapshot(
            start_time=self._start_time,
            uptime_seconds=max(self._clock() - self._start_time, 0.0),
            values={name: dict(series) for name, series in self._values.items()},
        )
