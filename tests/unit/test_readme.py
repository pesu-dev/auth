from unittest.mock import mock_open, patch
import pytest

import app.app as app_module

from fastapi.testclient import TestClient
from app.app import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_convert_readme_to_html_writes_html():
    m_open = mock_open(read_data="# Title\nSome content")
    with patch("builtins.open", m_open):
        with patch("gh_md_to_html.main") as mock_gh_md_to_html:
            mock_gh_md_to_html.return_value = "<h1>Title</h1>"
            app_module.util.convert_readme_to_html()
    m_open.assert_any_call("README_tmp.md", "w")
    m_open.assert_any_call("README.html", "w")
    handle = m_open()
    handle.write.assert_any_call("<h1>Title</h1>")


def test_readme_raises_exception(monkeypatch, client):
    def raise_exception():
        raise Exception("fail")

    monkeypatch.setattr("pathlib.Path.exists", lambda self: False)
    monkeypatch.setattr(app_module.util, "convert_readme_to_html", raise_exception)

    with pytest.raises(Exception):
        response = client.get("/readme")
        assert response.status_code == 500
        assert "Internal Server Error" in response.text


def test_readme_success(client):
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_text", return_value="<html><body>Test README</body></html>"),
    ):
        response = client.get("/readme")
        assert response.status_code == 200
        assert "html" in response.headers["content-type"]
        assert "Test README" in response.text


def test_readme_generates_html_when_missing(client):
    m_open = mock_open(read_data="# Title\nSome content")

    with (
        patch("pathlib.Path.exists", side_effect=[False, True]),
        patch("builtins.open", m_open),
        patch("app.util.gh_md_to_html.main", return_value="<h1>Generated Title</h1>"),
        patch("pathlib.Path.read_text", return_value="<h1>Generated Title</h1>"),
    ):
        response = client.get("/readme")
        assert response.status_code == 200
        assert "html" in response.headers["content-type"]
        assert "Generated Title" in response.text
