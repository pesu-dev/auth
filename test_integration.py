"""Test integration script."""

import asyncio
import json
import os

from dotenv import load_dotenv

from app.pesu import PESUAcademy

load_dotenv()


async def test_integration() -> None:
    """Run the integration test for PESUAcademy authentication."""
    pesu = PESUAcademy()
    username = os.getenv("TEST_EMAIL")
    password = os.getenv("TEST_PASSWORD")

    if not username or not password:
        print("Missing credentials in .env")
        return

    print(f"Testing authenticate for: {username}")
    result = await pesu.authenticate(
        username=username, password=password, profile=True, know_your_class_and_section=True
    )

    print("--- Authentication Result ---")
    print(json.dumps(result, indent=2))


asyncio.run(test_integration())
