"""Custom documentation module for PESUAuth API."""

from .authenticate import authenticate_docs
from .health import health_docs
from .readme import readme_docs

__all__ = [
    "authenticate_docs",
    "health_docs",
    "readme_docs",
]
