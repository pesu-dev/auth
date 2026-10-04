"""Verify release safety against mocked Render API responses."""

import importlib.util
import io
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from unittest.mock import Mock

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / ".github/scripts/render_deployment.py"
SHA = "a" * 40


@pytest.fixture
def helper(monkeypatch):
    spec = importlib.util.spec_from_file_location("render_deployment", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setenv("RENDER_API_KEY", "private-test-token")
    monkeypatch.setenv("RENDER_SERVICE_ID", "srv-test")
    return module


def response(body):
    result = Mock()
    result.__enter__ = Mock(return_value=io.BytesIO(json.dumps(body).encode()))
    result.__exit__ = Mock(return_value=False)
    return result


def deploy(status="live", deploy_id="dep-old", sha=SHA):
    return {"id": deploy_id, "status": status, "commit": {"id": sha}}


def api(helper, monkeypatch, *bodies):
    request = Mock(side_effect=[response(body) for body in bodies])
    monkeypatch.setattr(helper, "urlopen", request)
    return request


def test_validation_rejects_staging_commit_mismatch(helper, monkeypatch, capsys):
    api(helper, monkeypatch, [{"deploy": deploy(sha="b" * 40)}])
    assert helper.main(["validate-staging", "--target-sha", SHA]) == 1
    assert "staging" in capsys.readouterr().err.lower()


def test_validation_checks_live_deploy_not_newer_failed_attempt(helper, monkeypatch):
    api(helper, monkeypatch, [{"deploy": deploy("build_failed", "dep-failed", "b" * 40)}, {"deploy": deploy()}])
    assert helper.main(["validate-staging", "--target-sha", SHA]) == 0


def test_validation_fails_closed_when_no_live_deploy(helper, monkeypatch):
    api(helper, monkeypatch, [])
    assert helper.main(["validate-staging", "--target-sha", SHA]) == 1


def test_snapshot_records_live_deployment_for_rollback(helper, monkeypatch, tmp_path):
    output = tmp_path / "output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    api(helper, monkeypatch, [{"deploy": deploy("build_failed", "dep-failed")}, {"deploy": deploy()}])
    assert helper.main(["snapshot"]) == 0
    assert output.read_text() == "previous_deploy_id=dep-old\n"


def test_snapshot_fails_closed_without_previous_live_deploy(helper, monkeypatch, tmp_path):
    output = tmp_path / "output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    api(helper, monkeypatch, [])
    assert helper.main(["snapshot"]) == 1
    assert not output.exists()


def test_live_lookup_follows_pagination(helper, monkeypatch):
    bodies = [{"deploy": deploy("deactivated", f"dep-{i}"), "cursor": f"cursor-{i}"} for i in range(100)]
    request = api(helper, monkeypatch, bodies, [{"deploy": deploy()}])
    assert helper.main(["validate-staging", "--target-sha", SHA]) == 0
    assert "cursor=cursor-99" in request.call_args_list[1].args[0].full_url


def test_rollback_posts_retained_id_then_polls_returned_deploy(helper, monkeypatch):
    request = api(
        helper,
        monkeypatch,
        deploy("update_in_progress", "dep-rollback"),
        deploy("update_in_progress", "dep-rollback"),
        deploy("live", "dep-rollback"),
    )
    monkeypatch.setattr(helper.time, "sleep", Mock())
    assert helper.main(["rollback", "--deploy-id", "dep-old"]) == 0
    initial = request.call_args_list[0].args[0]
    assert initial.full_url == "https://api.render.com/v1/services/srv-test/rollback"
    assert initial.method == "POST"
    assert json.loads(initial.data) == {"deployId": "dep-old"}
    assert request.call_args_list[1].args[0].full_url.endswith("/deploys/dep-rollback")
    assert all(call.kwargs["timeout"] <= 30 for call in request.call_args_list)


@pytest.mark.parametrize("status", ["build_failed", "update_failed", "canceled", "pre_deploy_failed", "deactivated"])
def test_rollback_fails_on_terminal_failure(helper, monkeypatch, status):
    api(helper, monkeypatch, deploy(status, "dep-rollback"))
    assert helper.main(["rollback", "--deploy-id", "dep-old"]) == 1


def test_rollback_timeout_is_bounded(helper, monkeypatch):
    api(helper, monkeypatch, deploy("queued", "dep-rollback"))
    monkeypatch.setattr(helper.time, "monotonic", Mock(side_effect=[0, 1000]))
    assert helper.main(["rollback", "--deploy-id", "dep-old"]) == 1


@pytest.mark.parametrize(
    "failure",
    [
        HTTPError("https://example.com", 401, "private-test-token", {}, io.BytesIO(b"private-test-token")),
        URLError("private-test-token"),
    ],
)
def test_http_errors_never_expose_secrets(helper, monkeypatch, capsys, failure):
    monkeypatch.setattr(helper, "urlopen", Mock(side_effect=failure))
    assert helper.main(["validate-staging", "--target-sha", SHA]) == 1
    captured = capsys.readouterr()
    assert "private-test-token" not in captured.out + captured.err


def test_missing_credentials_fail_without_network(helper, monkeypatch, capsys):
    monkeypatch.delenv("RENDER_API_KEY")
    request = Mock()
    monkeypatch.setattr(helper, "urlopen", request)
    assert helper.main(["snapshot"]) == 1
    request.assert_not_called()
    assert "RENDER_API_KEY" in capsys.readouterr().err


def test_poll_http_failure_does_not_report_rollback_success(helper, monkeypatch):
    monkeypatch.setattr(helper.time, "sleep", Mock())
    request = api(helper, monkeypatch, deploy("queued", "dep-rollback"))
    request.side_effect = [response(deploy("queued", "dep-rollback")), URLError("failed")]
    assert helper.main(["rollback", "--deploy-id", "dep-old"]) == 1


@pytest.mark.parametrize(
    "body", [{"message": "private-test-token"}, ["private-test-token"], [{"deploy": "private-test-token"}]]
)
def test_invalid_deployment_list_fails_without_echoing_body(helper, monkeypatch, capsys, body):
    api(helper, monkeypatch, body)
    assert helper.main(["validate-staging", "--target-sha", SHA]) == 1
    captured = capsys.readouterr()
    assert "private-test-token" not in captured.out + captured.err


@pytest.mark.parametrize("body", [None, {"id": "dep-new\ninjected=secret", "status": "live"}, deploy("unexpected")])
def test_malformed_rollback_response_fails_closed(helper, monkeypatch, body):
    api(helper, monkeypatch, body)
    assert helper.main(["rollback", "--deploy-id", "dep-old"]) == 1


def test_poll_rejects_unrelated_deployment(helper, monkeypatch):
    api(helper, monkeypatch, deploy("queued", "dep-rollback"), deploy("live", "dep-unrelated"))
    monkeypatch.setattr(helper.time, "sleep", Mock())
    assert helper.main(["rollback", "--deploy-id", "dep-old"]) == 1


def test_invalid_json_diagnostic_does_not_expose_response(helper, monkeypatch, capsys):
    invalid = Mock()
    invalid.__enter__ = Mock(return_value=io.BytesIO(b"private-test-token"))
    invalid.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(helper, "urlopen", Mock(return_value=invalid))
    assert helper.main(["validate-staging", "--target-sha", SHA]) == 1
    assert "private-test-token" not in capsys.readouterr().err


def test_repeated_pagination_cursor_fails_closed(helper, monkeypatch):
    page = [{"deploy": deploy("deactivated"), "cursor": "cursor-same"} for _ in range(100)]
    api(helper, monkeypatch, page, page)
    assert helper.main(["validate-staging", "--target-sha", SHA]) == 1


def test_no_live_deployment_pagination_is_bounded(helper, monkeypatch):
    pages = [[{"deploy": deploy("deactivated"), "cursor": f"cursor-{i}"} for _ in range(100)] for i in range(10)]
    request = api(helper, monkeypatch, *pages)
    assert helper.main(["validate-staging", "--target-sha", SHA]) == 1
    assert request.call_count == 10


def test_invalid_target_sha_prevents_api_request(helper, monkeypatch):
    request = api(helper, monkeypatch)
    assert helper.main(["validate-staging", "--target-sha", "latest"]) == 1
    request.assert_not_called()


def test_snapshot_requires_output_path_before_api_request(helper, monkeypatch):
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    request = api(helper, monkeypatch)
    assert helper.main(["snapshot"]) == 1
    request.assert_not_called()


def test_snapshot_output_error_does_not_print_path(helper, monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "private-test-token" / "missing-output"))
    api(helper, monkeypatch, [{"deploy": deploy()}])
    assert helper.main(["snapshot"]) == 1
    assert "private-test-token" not in capsys.readouterr().err


@pytest.mark.parametrize("status", [[], {}, None])
def test_non_string_rollback_status_fails_without_traceback(helper, monkeypatch, status):
    api(helper, monkeypatch, deploy(status, "dep-rollback"))
    assert helper.main(["rollback", "--deploy-id", "dep-old"]) == 1


def test_redirect_handler_refuses_to_forward_authorization(helper):
    request = helper.Request(
        "https://api.render.com/v1/services/srv-test/deploys", headers={"Authorization": "Bearer private-test-token"}
    )
    with pytest.raises(helper.DeploymentError) as error:
        helper.NoRedirects().redirect_request(
            request, None, 302, "Found", {}, "https://untrusted.example/private-test-token"
        )
    assert "private-test-token" not in str(error.value)


def test_redirect_failure_is_reported_safely(helper, monkeypatch, capsys):
    monkeypatch.setattr(
        helper, "urlopen", Mock(side_effect=helper.DeploymentError("Render API unexpectedly redirected the request."))
    )
    assert helper.main(["validate-staging", "--target-sha", SHA]) == 1
    assert "redirected" in capsys.readouterr().err


def test_script_entrypoint_exits_nonzero_without_credentials(monkeypatch, capsys):
    import runpy
    import sys

    monkeypatch.delenv("RENDER_API_KEY", raising=False)
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "snapshot"])
    with pytest.raises(SystemExit) as error:
        runpy.run_path(str(SCRIPT), run_name="__main__")
    assert error.value.code == 1
    assert "RENDER_API_KEY" in capsys.readouterr().err
