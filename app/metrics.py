"""Metrics collector for tracking authentication successes, failures, and error types."""

import threading
from collections import defaultdict


class MetricsCollector:
    """Thread-safe metrics collector for tracking application performance and usage."""

    def __init__(self) -> None:
        """Initialize the metrics collector with thread safety."""
        self.lock = threading.Lock()
        self.metrics = defaultdict(int)

    def inc(self, key: str) -> None:
        """Increment a metric counter by 1.

        Args:
            key (str): The metric key to increment.
        """
        with self.lock:
            self.metrics[key] += 1

    def get(self) -> dict[str, int]:
        """Get a copy of all current metrics.

        Returns:
            dict[str, int]: Dictionary containing all metrics and their current values.
        """
        with self.lock:
            return dict(self.metrics)


# Global metrics instance
metrics = MetricsCollector()
