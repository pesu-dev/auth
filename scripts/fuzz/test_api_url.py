"""Fuzz the synthetic loopback target; run explicitly after starting scripts.fuzz.target."""

from __future__ import annotations

from typing import TYPE_CHECKING

import schemathesis
from hypothesis import seed, settings
from schemathesis.checks import not_a_server_error
from schemathesis.specs.openapi.checks import (
    content_type_conformance,
    response_schema_conformance,
    status_code_conformance,
)

if TYPE_CHECKING:
    from schemathesis import Case

# This module intentionally has a fixed local URL and fixed synthetic credentials. Never point
# an unsanitized reproduction configuration at a real deployment or use real credentials here.
schema = schemathesis.openapi.from_url(
    "http://127.0.0.1:8080/openapi.json",
    config=schemathesis.Config.from_dict(
        {"seed": 218, "cache": {"enabled": False}, "generation": {"mode": "all", "database": "none"}},
    ),
)
schema.config.output.sanitization.update(enabled=False)


@schema.parametrize()
@seed(218)
@settings(max_examples=500, database=None, deadline=None)
def test_api(case: Case) -> None:
    """Require every generated response to match the published OpenAPI contract.

    Args:
        case (Case): A Schemathesis-generated positive or negative API request.
    """
    case.call_and_validate(
        headers={"Authorization": "Bearer secret-token"},
        checks=[
            not_a_server_error,
            status_code_conformance,
            content_type_conformance,
            response_schema_conformance,
        ],
        allow_redirects=False,
    )
