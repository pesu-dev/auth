"""Tests for the benchmark scripts in scripts/benchmark/. Nothing here sends a real request."""

import argparse
import re
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx2
import matplotlib
import pandas as pd
import pytest

# The scripts import their helper as a sibling module, the way they are run from that directory
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "benchmark"))
matplotlib.use("Agg")

import analyze_benchmark  # noqa: E402
import benchmark_requests  # noqa: E402
import util  # noqa: E402

# --- util.resolve_output_path ---


def test_an_explicit_path_is_used_as_given(tmp_path):
    target = tmp_path / "nested" / "run.csv"

    assert util.resolve_output_path("script", "csv", output=str(target)) == target
    assert target.parent.is_dir()


def test_a_bare_filename_goes_in_the_output_directory(tmp_path):
    assert util.resolve_output_path("script", "csv", output="run.csv", output_dir=str(tmp_path)) == tmp_path / "run.csv"


@pytest.mark.parametrize(("tag", "suffix"), [(None, ""), ("baseline", "_baseline")])
def test_a_generated_name_is_timestamped_and_tagged(tmp_path, monkeypatch, tag, suffix):
    monkeypatch.setattr(util, "DEFAULT_OUTPUT_DIR", tmp_path / "results")

    path = util.resolve_output_path("benchmark_requests", "csv", tag=tag)

    assert path.parent == tmp_path / "results"
    assert path.parent.is_dir()
    assert re.fullmatch(rf"benchmark_requests_\d{{8}}_\d{{6}}{suffix}\.csv", path.name)


# --- util.make_request ---


@pytest.fixture
def http_client():
    """Replace httpx2.Client with a mock; `.post` and `.get` return whatever a test sets."""
    client = MagicMock()
    with patch.object(util.httpx2, "Client") as client_class:
        client_class.return_value.__enter__.return_value = client
        yield client


def test_authenticate_posts_the_test_credentials(http_client, monkeypatch):
    monkeypatch.setenv("TEST_PRN", "PES1201800001")
    monkeypatch.setenv("TEST_PASSWORD", "secret")
    http_client.post.return_value = httpx2.Response(200, json={"status": True})

    body, elapsed = util.make_request(host="http://api.test", profile=False)

    assert body == {"status": True}
    assert elapsed >= 0
    url = http_client.post.call_args.args[0]
    assert url == "http://api.test/authenticate"
    assert http_client.post.call_args.kwargs["json"] == {
        "username": "PES1201800001",
        "password": "secret",
        "profile": False,
    }


def test_other_routes_are_fetched_with_get(http_client):
    http_client.get.return_value = httpx2.Response(200, json={"status": True, "message": "ok"})

    body, _ = util.make_request(host="http://api.test", route="health")

    assert body["message"] == "ok"
    assert http_client.get.call_args.args[0] == "http://api.test/health"
    http_client.post.assert_not_called()


@pytest.mark.parametrize(("status", "success"), [(200, True), (502, False)])
def test_a_non_json_answer_is_summarised(http_client, status, success):
    http_client.get.return_value = httpx2.Response(status, text="<html>not json</html>")

    body, _ = util.make_request(route="readme")

    assert body == {"status": success, "text": "<html>not json</html>"}


# --- benchmark_requests ---


def _args(**overrides):
    args = benchmark_requests.build_parser().parse_args([])
    return argparse.Namespace(**{**vars(args), **overrides})


def test_the_benchmark_defaults():
    args = benchmark_requests.build_parser().parse_args([])

    assert (args.num_requests, args.max_workers, args.route, args.host) == (10, 10, "authenticate", "http://localhost:5000")
    assert args.parallel is False
    assert args.no_profile is False


def test_a_sequential_run_records_each_request(capsys):
    responses = iter([({"status": True}, 0.5), ({"status": False}, 1.5)])
    with patch.object(benchmark_requests, "make_request", side_effect=lambda **_: next(responses)) as request:
        success, times = benchmark_requests.run_benchmark(_args(num_requests=2, verbose=True, no_profile=True))

    assert (success, times) == ([1, 0], [0.5, 1.5])
    assert request.call_args.kwargs == {
        "profile": False,
        "host": "http://localhost:5000",
        "route": "authenticate",
        "timeout": 10.0,
    }
    assert "Response: {'status': False}" in capsys.readouterr().out


def test_a_parallel_run_skips_failed_requests(capsys):
    calls = iter([({"status": True}, 0.2), RuntimeError("connection refused"), ({"status": True}, 0.4)])

    def request(**_):
        outcome = next(calls)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    with patch.object(benchmark_requests, "make_request", side_effect=request):
        success, times = benchmark_requests.run_benchmark(_args(num_requests=3, parallel=True, max_workers=1))

    assert success == [1, 1]
    assert sorted(times) == [0.2, 0.4]
    assert "Request failed: connection refused" in capsys.readouterr().out


def test_results_are_written_as_csv(tmp_path, capsys):
    outfile = tmp_path / "run.csv"

    benchmark_requests.write_results([1, 0], [0.5, 1.5], outfile)

    assert outfile.read_text() == "status,time\n1,0.5\n0,1.5\n"
    out = capsys.readouterr().out
    assert "Successful requests: 1 out of 2" in out
    assert "Average time per request: 1.00 seconds" in out


def test_results_with_no_completed_request(tmp_path, capsys):
    """Every request can fail in the parallel runner; that used to divide by zero."""
    benchmark_requests.write_results([], [], tmp_path / "run.csv")

    out = capsys.readouterr().out
    assert "Successful requests: 0 out of 0" in out
    assert "Average time" not in out


def test_the_benchmark_from_the_command_line(tmp_path):
    with patch.object(benchmark_requests, "make_request", return_value=({"status": True}, 0.25)):
        benchmark_requests.main(["--num-requests", "2", "--output-dir", str(tmp_path), "--tag", "t"])

    (result,) = tmp_path.glob("benchmark_requests_*_t.csv")
    assert result.read_text() == "status,time\n1,0.25\n1,0.25\n"


# --- analyze_benchmark ---


@pytest.fixture
def results():
    return pd.DataFrame({"status": [1, 1, 0, 1], "time": [0.5, 1.0, 2.0, 1.5]})


def test_the_summary(results, capsys):
    analyze_benchmark.analyze_benchmark(results)

    out = capsys.readouterr().out
    assert "Total requests       : 4" in out
    assert "Failed requests      : 1" in out
    assert "Success rate         : 75.00%" in out
    assert "Avg time/successful : 1.000 sec" in out
    assert "Throughput           : 0.80 requests/sec" in out


def test_the_summary_of_instant_requests(capsys):
    analyze_benchmark.analyze_benchmark(pd.DataFrame({"status": [1], "time": [0.0]}))

    assert "Throughput           : inf requests/sec" in capsys.readouterr().out


@pytest.mark.parametrize("plot", [analyze_benchmark.plot_distribution, analyze_benchmark.plot_response_time_over_requests])
def test_each_plot_is_saved(results, tmp_path, plot):
    outfile = tmp_path / "plot.png"

    plot([results, results.copy()], ["a.csv", "b.csv"], outfile)

    assert outfile.read_bytes().startswith(b"\x89PNG")


def test_the_analysis_from_the_command_line(results, tmp_path, capsys):
    csv = tmp_path / "run.csv"
    results.to_csv(csv, index=False)

    analyze_benchmark.main(["-f", str(csv), "--output-dir", str(tmp_path), "--tag", "t"])

    assert len(list(tmp_path.glob("distribution_*_t.png"))) == 1
    assert len(list(tmp_path.glob("timeline_*_t.png"))) == 1
    assert "Benchmark Summary" in capsys.readouterr().out
