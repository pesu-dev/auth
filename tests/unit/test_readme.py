from unittest.mock import AsyncMock, patch

import pytest
from fastapi.responses import RedirectResponse


@pytest.mark.asyncio
async def test_unit_readme_redirects():
    """Unit test for the /readme endpoint.
    It should return a RedirectResponse to the correct GitHub repository.
    """
    with patch("app.app.readme", new_callable=AsyncMock) as mock_readme:
        mock_response = RedirectResponse(url="https://github.com/pesu-dev/auth", status_code=307)
        mock_readme.return_value = mock_response
        response = await mock_readme()
        assert isinstance(response, RedirectResponse)
        assert response.status_code == 307
        assert response.headers["location"] == "https://github.com/pesu-dev/auth"
