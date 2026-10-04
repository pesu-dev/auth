"""Validate staged commits and roll back to retained Render deployments.

Credentials are read only from the environment. API response bodies and exception
messages are deliberately excluded from diagnostics because they can contain secrets.
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

API_BASE = "https://api.render.com/v1"
HTTP_TIMEOUT = 30
POLL_TIMEOUT = 900
POLL_INTERVAL = 10
PAGE_SIZE = 100
MAX_PAGES = 10
FAILED_STATUSES = frozenset({"build_failed", "update_failed", "pre_deploy_failed", "canceled", "deactivated"})
PENDING_STATUSES = frozenset({"created", "queued", "build_in_progress", "update_in_progress", "pre_deploy_in_progress"})


class DeploymentError(RuntimeError):
    """A deployment operation failed with a safe, locally defined diagnostic."""


class NoRedirects(HTTPRedirectHandler):
    """Prevent an API redirect from forwarding the bearer token to another host."""

    def redirect_request(self, req: Request, fp: object, code: int, msg: str, headers: object, newurl: str) -> None:
        """Reject all redirects without including an untrusted destination in errors."""
        raise DeploymentError("Render API unexpectedly redirected the request.")


urlopen = build_opener(NoRedirects()).open


def identifier(value: object, prefix: str) -> str:
    """Validate an API identifier before using it in URLs or workflow outputs."""
    if not isinstance(value, str) or not re.fullmatch(rf"{prefix}-[A-Za-z0-9-]+", value):
        raise DeploymentError("Render returned an invalid deployment or service identifier.")
    return value


class RenderClient:
    """Minimal bounded Render API client for deployment safety checks."""

    def __init__(self) -> None:
        """Read required credentials without exposing their values."""
        token = os.environ.get("RENDER_API_KEY")
        service = os.environ.get("RENDER_SERVICE_ID")
        if not token or not service:
            raise DeploymentError("RENDER_API_KEY and RENDER_SERVICE_ID must be configured.")
        self.token = token
        self.service = identifier(service, "srv")

    def request(self, suffix: str, payload: dict[str, str] | None = None) -> object:
        """Request JSON while suppressing untrusted error bodies and messages."""
        request = Request(
            f"{API_BASE}/services/{self.service}/{suffix}",
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            method="POST" if payload is not None else "GET",
        )
        try:
            with urlopen(request, timeout=HTTP_TIMEOUT) as response:
                return json.loads(response.read(1_000_000))
        except HTTPError as error:
            raise DeploymentError(f"Render API request failed (HTTP {error.code}).") from None
        except URLError, TimeoutError, OSError:
            raise DeploymentError("Render API request failed or timed out.") from None
        except ValueError, UnicodeError:
            raise DeploymentError("Render API returned invalid JSON.") from None

    def live_deploy(self) -> dict[str, Any]:
        """Find the current live deployment, ignoring newer failed attempts."""
        cursor = None
        seen = set()
        for _ in range(MAX_PAGES):
            query = {"limit": PAGE_SIZE, "status": "live"}
            if cursor:
                query["cursor"] = cursor
            page = self.request(f"deploys?{urlencode(query)}")
            if not isinstance(page, list):
                raise DeploymentError("Render API returned an invalid deployment list.")
            for item in page:
                if not isinstance(item, dict) or not isinstance(item.get("deploy"), dict):
                    raise DeploymentError("Render API returned an invalid deployment list.")
                deploy = item["deploy"]
                if deploy.get("status") == "live":
                    identifier(deploy.get("id"), "dep")
                    return deploy
            if len(page) < PAGE_SIZE:
                break
            cursor = page[-1].get("cursor")
            if not isinstance(cursor, str) or not cursor or cursor in seen:
                raise DeploymentError("Render API returned invalid pagination.")
            seen.add(cursor)
        raise DeploymentError("No current live Render deployment found; refusing to proceed.")

    def rollback(self, deploy_id: str) -> None:
        """Restore a retained deployment and wait for its new deployment to become live."""
        previous_id = identifier(deploy_id, "dep")
        deadline = time.monotonic() + POLL_TIMEOUT
        deployment = self.request("rollback", {"deployId": previous_id})
        if not isinstance(deployment, dict):
            raise DeploymentError("Render API returned an invalid rollback deployment.")
        rollback_id = identifier(deployment.get("id"), "dep")
        while True:
            status = deployment.get("status")
            if status == "live":
                return
            if not isinstance(status, str):
                raise DeploymentError("Render rollback returned an invalid deployment state.")
            if status in FAILED_STATUSES:
                raise DeploymentError("Render rollback reached a failed or inactive state.")
            if status not in PENDING_STATUSES:
                raise DeploymentError("Render rollback returned an unknown deployment state.")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise DeploymentError("Timed out waiting for the Render rollback to become live.")
            time.sleep(min(POLL_INTERVAL, remaining))
            deployment = self.request(f"deploys/{rollback_id}")
            if not isinstance(deployment, dict) or deployment.get("id") != rollback_id:
                raise DeploymentError("Render API returned an invalid rollback deployment.")


def main(argv: list[str] | None = None) -> int:
    """Run the requested release safety check, returning a process exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate-staging")
    validate.add_argument("--target-sha", required=True)
    commands.add_parser("snapshot")
    rollback = commands.add_parser("rollback")
    rollback.add_argument("--deploy-id", required=True)
    args = parser.parse_args(argv)
    try:
        client = RenderClient()
        if args.command == "validate-staging":
            if not re.fullmatch(r"[0-9a-fA-F]{40}", args.target_sha):
                raise DeploymentError("The target commit must be a full Git SHA.")
            deployment = client.live_deploy()
            commit = deployment.get("commit")
            if not isinstance(commit, dict) or commit.get("id") != args.target_sha:
                raise DeploymentError("The target commit is not the current live staging deployment.")
            print("Confirmed the target commit is live on staging.")
        elif args.command == "snapshot":
            output = os.environ.get("GITHUB_OUTPUT")
            if not output:
                raise DeploymentError("GITHUB_OUTPUT must be configured to capture the previous deployment.")
            deploy_id = client.live_deploy()["id"]
            with Path(output).open("a", encoding="utf-8") as handle:
                handle.write(f"previous_deploy_id={deploy_id}\n")
            print("Captured the current live deployment for rollback.")
        else:
            client.rollback(args.deploy_id)
            print("Render rollback is live.")
    except DeploymentError as error:
        print(str(error), file=sys.stderr)
        return 1
    except OSError:
        print("Unable to write the deployment snapshot output.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
