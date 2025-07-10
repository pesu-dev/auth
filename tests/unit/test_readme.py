from unittest.mock import mock_open, patch
import pytest

import app.app as app_module
from fastapi import HTTPException


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


@pytest.mark.asyncio()
async def test_readme_raises_exception(monkeypatch):
    def raise_exception():
        raise Exception("fail")

    monkeypatch.setattr("pathlib.Path.exists", lambda self: False)
    monkeypatch.setattr(app_module.util, "convert_readme_to_html", raise_exception)
    with pytest.raises(HTTPException) as exc_info:
        await app_module.readme()

    assert exc_info.value.status_code == 500
    assert "Internal Server Error" in exc_info.value.detail
