from cachetools import TTLCache
import httpx
from selectolax.parser import HTMLParser

# Cache for CSRF token (expires after 5 minutes)
csrf_cache = TTLCache(maxsize=1, ttl=300)


async def get_csrf_token() -> str:
    """
    Return a cached CSRF token, fetching a new one if necessary.
    """
    if "csrf" in csrf_cache:
        return csrf_cache["csrf"]

    logging.info("Fetching a new unauthenticated CSRF token...")
    async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
        resp = await client.get("https://www.pesuacademy.com/Academy/")
        soup = HTMLParser(resp.text)
        node = soup.css_first("meta[name='csrf-token']")
        if not node:
            raise RuntimeError("CSRF token not found on PESU Academy homepage")
        token = node.attributes["content"]
        csrf_cache["csrf"] = token
        logging.info(f"Fetched and cached CSRF token: {token}")
        return token
