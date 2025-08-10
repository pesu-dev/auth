"""This module defines the class for API documentation purposes across different endpoints."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ApiDocs:
    """Represents the base API documentation class holding example requests and responses."""

    request_examples: dict
    response_examples: dict
