"""Tests for the benchmark scripts in scripts/benchmark/. Nothing here sends a real request."""

import re
import sys
from unittest.mock import MagicMock, patch

import httpx2
import matplotlib
import pandas as pd
import pytest

matplotlib.use("Agg")


def test_loading_the_scripts_leaves_no_trace(benchmark_dir, benchmark_util):
    assert str(benchmark_dir) not in sys.path
    assert sys.modules.get("util") is not benchmark_util


def test_an_explicit_path_is_used_as_given(benchmark_util, tmp_path):
    target = tmp_path / "nested" / "run.csv"

    assert benchmark_util.resolve_output_path("script", "csv", output=str(target)) == target
    assert target.parent.is_dir()


def test_a_bare_filename_goes_in_the_output_directory(benchmark_util, tmp_path):
    path = benchmark_util.resolve_output_path("script", "csv", output="run.csv", output_dir=str(tmp_path))

    assert path == tmp_path / "run.csv"


@pytest.mark.parametrize(("tag", "suffix"), [(None, ""), ("baseline", "_baseline")])
def test_a_generated_name_is_timestamped_and_tagged(benchmark_util, tmp_path, monkeypatch, tag, suffix):
    monkeypatch.setattr(benchmark_util, "DEFAULT_OUTPUT_DIR", tmp_path / "results")

    path = benchmark_util.resolve_output_path("benchmark_requests", "csv", tag=tag)

    assert path.parent == tmp_path / "results"
    assert path.parent.is_dir()
    assert re.fullmatch(rf"benchmark_requests_\d{{8}}_\d{{6}}{suffix}\.csv", path.name)


@pytest.fixture
def http_client(benchmark_util):
    """Replace httpx2.Client with a mock; `.post` and `.get` return whatever a test sets."""
    client = MagicMock()
    with patch.object(benchmark_util.httpx2, "Client") as client_class:
        client_class.return_value.__enter__.return_value = client
        yield client


def test_authenticate_posts_the_test_credentials(benchmark_util, http_client, monkeypatch):
    monkeypatch.setenv("TEST_PRN", "PES1201800001")
    monkeypatch.setenv("TEST_PASSWORD", "secret")
    http_client.post.return_value = httpx2.Response(200, json={"status": True})

    body, elapsed = benchmark_util.make_request(host="http://api.test", profile=False)

    assert body == {"status": True}
    assert elapsed >= 0
    url = http_client.post.call_args.args[0]
    assert url == "http://api.test/authenticate"
    assert http_client.post.call_args.kwargs["json"] == {
        "username": "PES1201800001",
        "password": "secret",
        "profile": False,
    }


def test_other_routes_are_fetched_with_get(benchmark_util, http_client):
    http_client.get.return_value = httpx2.Response(200, json={"status": True, "message": "ok"})

    body, _ = benchmark_util.make_request(host="http://api.test", route="health")

    assert body["message"] == "ok"
    assert http_client.get.call_args.args[0] == "http://api.test/health"
    http_client.post.assert_not_called()


@pytest.mark.parametrize(("status", "success"), [(200, True), (502, False)])
def test_a_non_json_answer_is_summarised(benchmark_util, http_client, status, success):
    http_client.get.return_value = httpx2.Response(status, text="<html>not json</html>")

    body, _ = benchmark_util.make_request(route="readme")

    assert body == {"status": success, "text": "<html>not json</html>"}


def _run_benchmark(benchmark_requests, monkeypatch, tmp_path, *args, request):
    """Run the benchmark's command line with make_request replaced, and return its CSV and output."""
    monkeypatch.setattr(sys, "argv", ["benchmark_requests.py", "--output-dir", str(tmp_path), "--tag", "t", *args])
    with patch.object(benchmark_requests, "make_request", side_effect=request) as make_request:
        benchmark_requests.main()
    (result,) = tmp_path.glob("benchmark_requests_*_t.csv")
    return result.read_text(), make_request


def _rows(csv):
    """The CSV's header, and its rows as (status, time) pairs and start offsets, in file order."""
    header, *lines = csv.splitlines()
    rows = [line.split(",") for line in lines]
    return header, [f"{status},{time}" for status, time, _ in rows], [float(start) for *_, start in rows]


@pytest.fixture
def clock(benchmark_requests, monkeypatch):
    """Make time.perf_counter return the given readings in turn, so elapsed times are exact."""

    def set_readings(*readings):
        values = iter(readings)
        monkeypatch.setattr(benchmark_requests.time, "perf_counter", lambda: next(values))

    return set_readings


def test_a_sequential_run_records_each_request(benchmark_requests, monkeypatch, tmp_path, capsys):
    responses = iter([({"status": True}, 0.5), ({"status": False}, 1.5)])

    csv, make_request = _run_benchmark(
        benchmark_requests,
        monkeypatch,
        tmp_path,
        "--num-requests",
        "2",
        "--verbose",
        "--no-profile",
        request=lambda **_: next(responses),
    )

    header, rows, starts = _rows(csv)
    assert (header, rows) == ("status,time,start", ["1,0.5", "0,1.5"])
    # Each request's start, from the start of the run: in order, since they ran one after another
    assert starts == sorted(starts)
    assert all(start >= 0 for start in starts)
    assert make_request.call_args.kwargs == {
        "profile": False,
        "host": "http://localhost:5000",
        "route": "authenticate",
        "timeout": 10.0,
    }
    out = capsys.readouterr().out
    assert "Response: {'status': False}" in out
    assert "Successful requests: 1 out of 2" in out
    assert "Average time per request: 1.00 seconds" in out


def test_a_parallel_run_skips_failed_requests(benchmark_requests, monkeypatch, tmp_path, capsys):
    calls = iter([({"status": True}, 0.2), RuntimeError("connection refused"), ({"status": False}, 0.4)])

    def request(**_):
        outcome = next(calls)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    csv, _ = _run_benchmark(
        benchmark_requests,
        monkeypatch,
        tmp_path,
        "--num-requests",
        "3",
        "--parallel",
        "--max-workers",
        "1",
        "--verbose",
        request=request,
    )

    header, rows, starts = _rows(csv)
    assert header == "status,time,start"
    assert sorted(rows) == ["0,0.4", "1,0.2"]
    # Only completed requests are written, each with its start
    assert len(starts) == 2
    out = capsys.readouterr().out
    assert "Request failed: connection refused" in out
    assert "Response: {'status': True}" in out


def test_a_parallel_run_prints_no_responses_unless_verbose(benchmark_requests, monkeypatch, tmp_path, capsys):
    csv, _ = _run_benchmark(
        benchmark_requests,
        monkeypatch,
        tmp_path,
        "--num-requests",
        "2",
        "--parallel",
        request=lambda **_: ({"status": True}, 0.1),
    )

    assert _rows(csv)[:2] == ("status,time,start", ["1,0.1", "1,0.1"])
    assert "Response:" not in capsys.readouterr().out


def test_a_parallel_run_with_no_completed_request(benchmark_requests, monkeypatch, tmp_path, capsys):
    """Every request can fail in the parallel runner; that used to divide by zero."""

    def request(**_):
        raise RuntimeError("connection refused")

    csv, _ = _run_benchmark(
        benchmark_requests, monkeypatch, tmp_path, "--num-requests", "2", "--parallel", request=request
    )

    assert csv == "status,time,start\n"
    out = capsys.readouterr().out
    assert "Successful requests: 0 out of 0" in out
    assert "Average time" not in out
    assert "Throughput: 0.00 requests/second" in out


def test_elapsed_time_and_throughput_come_from_the_clock_not_the_latencies(
    benchmark_requests, monkeypatch, tmp_path, capsys, clock
):
    """Throughput is requests over the run's elapsed time, not over the sum of their latencies.

    In a parallel run the latencies overlap, so their sum is many times what the run took; using it
    made throughput look a fraction of what it was.
    """
    # The run starts at 100 s; the requests start 1 s apart; the run ends at 104 s
    clock(100.0, 100.0, 101.0, 104.0)

    csv, _ = _run_benchmark(
        benchmark_requests,
        monkeypatch,
        tmp_path,
        "--num-requests",
        "2",
        request=lambda **_: ({"status": True}, 3.0),
    )

    assert csv == "status,time,start\n1,3.0,0.0\n1,3.0,1.0\n"
    out = capsys.readouterr().out
    assert "Elapsed time: 4.00 seconds" in out
    # 2 requests in 4 s, though their latencies add up to 6 s
    assert "Throughput: 0.50 requests/second" in out


def test_the_benchmark_defaults(benchmark_requests, monkeypatch, tmp_path):
    _, make_request = _run_benchmark(
        benchmark_requests, monkeypatch, tmp_path, request=lambda **_: ({"status": True}, 0.25)
    )

    assert make_request.call_count == 10
    assert make_request.call_args.kwargs == {
        "profile": True,
        "host": "http://localhost:5000",
        "route": "authenticate",
        "timeout": 10.0,
    }


@pytest.fixture
def results():
    return pd.DataFrame({"status": [1, 1, 0, 1], "time": [0.5, 1.0, 2.0, 1.5]})


def test_the_summary(analyze_benchmark, results, capsys):
    # Four overlapping requests, as a parallel run makes them: the run took 2.5 s, not 5 s
    analyze_benchmark.analyze_benchmark(results.assign(start=[0.0, 0.0, 0.5, 1.0]))

    out = capsys.readouterr().out
    assert "Total requests       : 4" in out
    assert "Failed requests      : 1" in out
    assert "Success rate         : 75.00%" in out
    assert "Avg time/successful : 1.000 sec" in out
    assert "Elapsed time         : 2.500 sec\n" in out
    assert "Throughput           : 1.60 requests/sec" in out


def test_the_summary_of_a_csv_without_start_times(analyze_benchmark, results, capsys):
    """Older CSVs have no start column: the latencies' sum stands in, and the summary says so."""
    analyze_benchmark.analyze_benchmark(results)

    out = capsys.readouterr().out
    assert "Elapsed time         : 5.000 sec (sum of latencies" in out
    assert "Throughput           : 0.80 requests/sec" in out


def test_the_summary_of_instant_requests(analyze_benchmark, capsys):
    analyze_benchmark.analyze_benchmark(pd.DataFrame({"status": [1], "time": [0.0]}))

    assert "Throughput           : inf requests/sec" in capsys.readouterr().out


@pytest.mark.parametrize("plot", ["plot_distribution", "plot_response_time_over_requests"])
def test_each_plot_is_saved(analyze_benchmark, results, tmp_path, plot):
    outfile = tmp_path / "plot.png"

    getattr(analyze_benchmark, plot)([results, results.copy()], ["a.csv", "b.csv"], outfile)

    assert outfile.read_bytes().startswith(b"\x89PNG")


def test_the_analysis_from_the_command_line(analyze_benchmark, results, tmp_path, capsys, monkeypatch):
    csv = tmp_path / "run.csv"
    results.to_csv(csv, index=False)

    monkeypatch.setattr(
        sys, "argv", ["analyze_benchmark.py", "-f", str(csv), "--output-dir", str(tmp_path), "--tag", "t"]
    )
    analyze_benchmark.main()

    assert len(list(tmp_path.glob("distribution_*_t.png"))) == 1
    assert len(list(tmp_path.glob("timeline_*_t.png"))) == 1
    assert "Benchmark Summary" in capsys.readouterr().out
