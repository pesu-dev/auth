import asyncio
import logging
import aiofiles
import emoji
import httpx


async def convert_readme_to_html() -> str:
    """
    Convert the README.md file to HTML using GitHub's Markdown API and return it.
    """
    logging.info("Beginning conversion of README.md to HTML via GitHub API...")
    async with aiofiles.open("README.md", mode="r", encoding="utf-8") as f:
        readme_content = await f.read()
    readme_content = await asyncio.to_thread(emoji.emojize, readme_content.strip(), language="alias")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.github.com/markdown",
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json={"text": readme_content},
            timeout=10.0,
        )
        response.raise_for_status()
        html = response.text.strip()
    return html
