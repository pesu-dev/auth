"""Test new endpoint script."""

import asyncio
import os

import httpx
from dotenv import load_dotenv

load_dotenv()


async def test_httpx() -> None:
    """Run the http test against PESUAcademy endpoints."""
    url = "https://www.pesuacademy.com/MAcademy/mobile/mobilelogin/auth"

    username = os.getenv("TEST_EMAIL")
    password = os.getenv("TEST_PASSWORD")

    if not username or not password:
        print("Error: TEST_EMAIL or TEST_PASSWORD not found in .env file")
        return

    files = {
        "userName": (None, username),
        "password": (None, password),
        "j_appId": (None, "YES"),
        "instId": (None, "1,6,7,14"),
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, files=files)
        print("Login status code:", resp.status_code)

        token = resp.headers.get("mobileappauthenticationtoken")

        try:
            data = resp.json()
            mobile_obj = data.get("mobileJsonObject", {})
            user_id = mobile_obj.get("userId")
            bearer_token = data.get("accessToken") or mobile_obj.get("accessToken")
            print("Login success:", mobile_obj.get("login"))
            print("Token:", token is not None)
            disp_url = "https://www.pesuacademy.com/MAcademy/mobile/dispatcher"
            disp_headers = {"authorization": f"Bearer {bearer_token}", "mobileappauthenticationtoken": token}
            disp_files = {
                "action": (None, "27"),
                "mode": (None, "1"),
                "userId": (None, user_id),
                "searchUserId": (None, user_id),
            }
            disp_resp = await client.post(disp_url, headers=disp_headers, files=disp_files)
            print("Dispatcher status code:", disp_resp.status_code)
            disp_data = disp_resp.json()
            print("Dispatcher message:", disp_data.get("MESSAGE"))
            student = disp_data.get("STUDENT_PHOTO", {})
            print("Name:", student.get("nameAsInSSLC"))

        except Exception as e:
            print("Error parsing json:", e)
            print(resp.text)


asyncio.run(test_httpx())
