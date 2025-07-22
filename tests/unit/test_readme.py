import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from app.app import app
import app.util as util
import app.app as app_module


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_convert_readme_to_html_returns_html():
    mock_file = AsyncMock()
    mock_file.__aenter__.return_value.read.return_value = "# Title\nSome content"
    with patch("emoji.emojize", return_value="# Title\nSome content"):
        mock_response = MagicMock()
        mock_response.text = "<h1>Mock HTML</h1>"
        mock_response.raise_for_status = lambda: None  # avoid exception
        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_response
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client_instance
        with (
            patch("aiofiles.open", return_value=mock_file),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            html = await util.convert_readme_to_html()
            assert html == "<h1>Mock HTML</h1>"
            mock_file.__aenter__.return_value.read.assert_awaited_once()
            mock_client_instance.post.assert_awaited_once()


def test_readme_raises_exception(monkeypatch, client):
    async def raise_exception():
        raise Exception("fail")

    monkeypatch.setattr(util, "convert_readme_to_html", raise_exception)
    app_module.README_HTML_CACHE = None
    response = client.get("/readme")
    assert response.status_code == 500
    assert "Internal Server Error" in response.text


def test_readme_success(client):
    cached_html = '<div class="markdown-heading"><h1 class="heading-element">pesu-auth</h1></div>'
    app_module.README_HTML_CACHE = cached_html
    response = client.get("/readme")
    assert response.status_code == 200
    assert "html" in response.headers["content-type"]
    assert "pesu-auth" in response.text


def test_readme_generates_html_when_missing(client):
    app_module.README_HTML_CACHE = None
    generated_html = (
        '<div class="markdown-heading"><h1 class="heading-element">Generated Title</h1></div>'
    )
    with patch("app.util.convert_readme_to_html", new_callable=AsyncMock) as mock_convert:
        mock_convert.return_value = generated_html
        response = client.get("/readme")
    assert response.status_code == 200
    assert "html" in response.headers["content-type"]
    assert "Generated Title" in response.text
