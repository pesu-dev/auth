"""Unit tests for the metrics collector."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.metrics import MetricsCollector


class TestMetricsCollector:
    """Test cases for the MetricsCollector class."""

    def test_init(self):
        """Test that MetricsCollector initializes correctly."""
        collector = MetricsCollector()
        assert collector.get() == {}

    def test_increment_single_metric(self):
        """Test incrementing a single metric."""
        collector = MetricsCollector()
        collector.inc("test_metric")
        assert collector.get() == {"test_metric": 1}

    def test_increment_multiple_times(self):
        """Test incrementing the same metric multiple times."""
        collector = MetricsCollector()
        collector.inc("test_metric")
        collector.inc("test_metric")
        collector.inc("test_metric")
        assert collector.get() == {"test_metric": 3}

    def test_increment_different_metrics(self):
        """Test incrementing different metrics."""
        collector = MetricsCollector()
        collector.inc("auth_success_total")
        collector.inc("auth_failure_total")
        collector.inc("auth_success_total")
        
        expected = {
            "auth_success_total": 2,
            "auth_failure_total": 1,
        }
        assert collector.get() == expected

    def test_get_returns_copy(self):
        """Test that get() returns a copy of metrics, not the original."""
        collector = MetricsCollector()
        collector.inc("test_metric")
        
        metrics1 = collector.get()
        metrics2 = collector.get()
        
        # Modify one copy
        metrics1["new_key"] = 999
        
        # Original collector and second copy should be unaffected
        assert collector.get() == {"test_metric": 1}
        assert metrics2 == {"test_metric": 1}

    def test_thread_safety(self):
        """Test that metrics collection is thread-safe."""
        collector = MetricsCollector()
        
        def increment_metrics():
            for _ in range(100):
                collector.inc("thread_test")
        
        # Run 10 threads, each incrementing 100 times
        num_threads = 10
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(increment_metrics) for _ in range(num_threads)]
            for future in futures:
                future.result()
        
        # Should have exactly 1000 increments (10 threads * 100 increments each)
        assert collector.get()["thread_test"] == 1000

    def test_concurrent_different_metrics(self):
        """Test concurrent access to different metrics."""
        collector = MetricsCollector()
        
        def increment_metric_a():
            for _ in range(50):
                collector.inc("metric_a")
        
        def increment_metric_b():
            for _ in range(75):
                collector.inc("metric_b")
        
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_a = executor.submit(increment_metric_a)
            future_b = executor.submit(increment_metric_b)
            future_a.result()
            future_b.result()
        
        metrics = collector.get()
        assert metrics["metric_a"] == 50
        assert metrics["metric_b"] == 75

    def test_concurrent_get_and_inc(self):
        """Test concurrent get() and inc() operations."""
        collector = MetricsCollector()
        results = []
        
        def increment_continuously():
            for i in range(100):
                collector.inc("concurrent_test")
                if i % 10 == 0:  # Occasionally sleep to allow other threads
                    time.sleep(0.001)
        
        def read_metrics():
            for _ in range(10):
                results.append(collector.get())
                time.sleep(0.01)
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            # Start two incrementing threads and one reading thread
            inc_future1 = executor.submit(increment_continuously)
            inc_future2 = executor.submit(increment_continuously)
            read_future = executor.submit(read_metrics)
            
            inc_future1.result()
            inc_future2.result()
            read_future.result()
        
        # Final count should be 200 (2 threads * 100 increments each)
        assert collector.get()["concurrent_test"] == 200
        
        # All read results should be valid (no exceptions during concurrent access)
        assert len(results) == 10
        for result in results:
            assert isinstance(result, dict)
            if "concurrent_test" in result:
                assert isinstance(result["concurrent_test"], int)
                assert result["concurrent_test"] >= 0

    def test_empty_string_metric_key(self):
        """Test handling of edge case metric keys."""
        collector = MetricsCollector()
        collector.inc("")  # Empty string key
        collector.inc("normal_key")
        
        metrics = collector.get()
        assert metrics[""] == 1
        assert metrics["normal_key"] == 1

    def test_special_character_metric_keys(self):
        """Test metric keys with special characters."""
        collector = MetricsCollector()
        special_keys = ["key.with.dots", "key-with-dashes", "key_with_underscores", "key with spaces"]
        
        for key in special_keys:
            collector.inc(key)
        
        metrics = collector.get()
        for key in special_keys:
            assert metrics[key] == 1
