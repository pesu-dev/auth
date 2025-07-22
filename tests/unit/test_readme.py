import pytest
from unittest.mock import AsyncMock, patch, mock_open
from fastapi.testclient import TestClient
from app.app import app
import app.util as util

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.mark.asyncio
async def test_convert_readme_to_html_returns_html():
    mock_readme_content = "# Title\nSome content"
    expected_html = "<h1>Title</h1>"

    m_open = mock_open(read_data=mock_readme_content)

    with patch("aiofiles.open", m_open), \
         patch("app.util.httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post, \
         patch("app.util.emoji.emojize", new_callable=AsyncMock) as mock_emojize:

        mock_emojize.return_value = mock_readme_content.strip()
        mock_post.return_value.text = expected_html

        html = await util.convert_readme_to_html()
        assert html == expected_html

    m_open.assert_called_once_with("README.md", mode="r", encoding="utf-8")


def test_readme_raises_exception(monkeypatch, client):
    async def raise_exception():
        raise Exception("fail")

    monkeypatch.setattr(util, "convert_readme_to_html", raise_exception)

    # Reset cached README_HTML_CACHE to None
    import app.app as app_module
    app_module.README_HTML_CACHE = None

    response = client.get("/readme")
    assert response.status_code == 500
    assert "Internal Server Error" in response.text


def test_readme_success(client):
    # Patch the global README_HTML_CACHE to simulate cached content
    import app.app as app_module
    cached_html = '<div class="markdown-heading"><h1 class="heading-element">pesu-auth</h1></div>'
    app_module.README_HTML_CACHE = cached_html

    response = client.get("/readme")
    assert response.status_code == 200
    assert "html" in response.headers["content-type"]
    assert "pesu-auth" in response.text


def test_readme_generates_html_when_missing(client):
    # Clear the cached global to force regeneration
    import app.app as app_module
    app_module.README_HTML_CACHE = None

    # Patch convert_readme_to_html to return generated HTML
    generated_html = '<div class="markdown-heading"><h1 class="heading-element">Generated Title</h1></div>'

    with patch("app.util.convert_readme_to_html", new_callable=AsyncMock) as mock_convert:
        mock_convert.return_value = generated_html
        response = client.get("/readme")

    assert response.status_code == 200
    assert "html" in response.headers["content-type"]
    assert "Generated Title" in response.text
