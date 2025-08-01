import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.app import readme
import app.app as app_module
from fastapi import FastAPI
from fastapi.responses import RedirectResponse

@pytest.mark.asyncio
async def test_unit_readme_redirects():
    """
    Unit test for the /readme endpoint.
    It should return a RedirectResponse to the correct GitHub repository.
    """
    response = await readme()
    assert isinstance(response, RedirectResponse)
    assert response.status_code == 307
    assert response.headers["location"] == "https://github.com/pesu-dev/auth"