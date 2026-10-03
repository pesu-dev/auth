"""Enable informational OpenAPI schema coverage for the mocked CLI target."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import schemathesis
import tracecov

from scripts.fuzz.target import SYNTHETIC_TOKEN

if TYPE_CHECKING:
    from schemathesis import Case
    from schemathesis.hooks import HookContext

tracecov.schemathesis.install()

# Unsanitized output is permitted only for the synthetic token. Validate without including an
# unexpected value in the error, so accidental real credentials never reach reproduction output.
if os.environ.get("API_TOKEN") != SYNTHETIC_TOKEN:
    raise ValueError("The local fuzz configuration requires the synthetic API_TOKEN from scripts.fuzz.target.")


@schemathesis.hook
def before_call(context: HookContext, case: Case, kwargs: dict[str, Any]) -> None:
    """Validate redirects themselves without ever following the GitHub Location header.

    Args:
        context (HookContext): Hook invocation context.
        case (Case): Generated request to the synthetic target.
        kwargs (dict[str, Any]): Mutable transport options.

    Raises:
        ValueError: If an override tries to send unsanitized requests outside the mocked target.
    """
    if case.operation.base_url != "http://127.0.0.1:8080":
        raise ValueError("The local fuzz configuration can only call the mocked loopback target.")
    # requests computes a next redirect even with allow_redirects=False. max_redirects=0 raises
    # TooManyRedirects during that computation, so disable following in transport instead.
    kwargs["allow_redirects"] = False
