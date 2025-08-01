import os
import time

import httpx
from dotenv import load_dotenv

load_dotenv()


def make_request(
    host: str = "http://localhost:5000",
    route: str = "authenticate",
    profile: bool = True,
    timeout: float = 10.0,
) -> tuple[dict, float]:
    """
    Make a request to the authentication endpoint and return the response and elapsed time.

    Args:
        host: The host to make the request to
        route: The route to make the request to
        profile: Whether to fetch the profile information or not
        timeout: The timeout for the request

    Returns:
        Tuple of response JSON and elapsed time in seconds
    """
    with httpx.Client(follow_redirects=True, timeout=httpx.Timeout(timeout)) as client:
        if route == "authenticate":
            data = {
                "username": os.getenv("TEST_PRN"),
                "password": os.getenv("TEST_PASSWORD"),
                "profile": profile,
            }
            start_time = time.time()
            response = client.post(
                f"{host}/{route}",
                json=data,
                follow_redirects=True,
            )
        else:
            start_time = time.time()
            response = client.get(
                f"{host}/{route}",
                follow_redirects=True,
            )
    elapsed_time = time.time() - start_time
    return response.json(), elapsed_time
