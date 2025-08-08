"""PESUAcademy class that serves as an interface to the PESU Academy website."""

import asyncio
import re
import time
from datetime import datetime
from typing import Any

import httpx
from selectolax.parser import HTMLParser, Node

from app.config import settings
from app.exceptions.authentication import (
    AuthenticationError,
    CSRFTokenError,
    ProfileFetchError,
    ProfileParseError,
)
from app.middleware.logging import get_logger
from app.middleware.metrics import PROFILE_FETCH_DURATION, record_csrf_operation, record_pesu_academy_request

logger = get_logger("pesu")


class PESUAcademy:
    """Class to interact with the PESU Academy server.

    This class provides methods to authenticate users, fetch profile information, and handle CSRF token management.

    Attributes:
        DEFAULT_FIELDS (list[str]): The default fields to fetch from the profile page.
        PROFILE_PAGE_HEADER_TO_KEY_MAP (dict[str, str]): A mapping of profile page headers to the corresponding keys
        in the profile dictionary.

    Methods:
        prefetch_client_with_csrf_token: Prefetch a new client with an unauthenticated CSRF token.
        close_client: Close the internal client if it exists.
        get_profile_information: Get the profile information of the user.
        authenticate: Authenticate the user with the provided username and password.
    """

    DEFAULT_FIELDS: list[str] = [
        "name",
        "prn",
        "srn",
        "program",
        "branch",
        "semester",
        "section",
        "email",
        "phone",
        "campus_code",
        "campus",
    ]

    PROFILE_PAGE_HEADER_TO_KEY_MAP = {
        "Name": "name",
        "PESU Id": "prn",
        "SRN": "srn",
        "Program": "program",
        "Branch": "branch",
        "Semester": "semester",
        "Section": "section",
    }

    def __init__(self) -> None:
        """Initialize the PESUAcademy class."""
        self._csrf_token: str | None = None
        self._client: httpx.AsyncClient | None = None
        self._csrf_lock = asyncio.Lock()

    @staticmethod
    async def _fetch_new_client_with_csrf_token() -> tuple[httpx.AsyncClient, str]:
        """Initialize a fresh client with an unauthenticated CSRF token from PESU Academy."""
        logger.info("Fetching a new client with an unauthenticated CSRF token")
        # Create a new client
        client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=settings.pesu_academy_timeout
        )
        # Fetch the CSRF token
        try:
            resp = await client.get(settings.pesu_academy_base_url)
            record_pesu_academy_request("base_url", resp.status_code)

            soup = await asyncio.to_thread(HTMLParser, resp.text)
            if node := soup.css_first("meta[name='csrf-token']"):
                csrf_token = node.attributes["content"]
                logger.info("Fetched CSRF token successfully", token_length=len(csrf_token))
                record_csrf_operation("fetch_success")
                return client, csrf_token
            record_csrf_operation("fetch_error")
            raise CSRFTokenError("CSRF token not found in the pre-authentication response.")
        except Exception as e:
            if resp:
                record_pesu_academy_request("base_url", getattr(resp, "status_code", 0))
            record_csrf_operation("fetch_error")
            logger.error("Failed to fetch CSRF token", error=str(e))
            raise

    async def _prefetch_client_with_csrf_token(self) -> None:
        """Prefetch a new client with an unauthenticated CSRF token.

        This method is used to prefetch a new client with an unauthenticated CSRF token.
        It is used to avoid the overhead of fetching a new client with an unauthenticated CSRF token
        for each request.
        """
        logger.info("Prefetching a new client with an unauthenticated CSRF token")
        client, token = await self._fetch_new_client_with_csrf_token()
        async with self._csrf_lock:
            # Close old cached client (if any) to avoid leaks
            if self._client is not None:
                await self._client.aclose()
            # Store the new cached client/token
            self._client = client
            self._csrf_token = token
        logger.info("Cache refreshed with new unauthenticated CSRF token")
        record_csrf_operation("cache_refresh")

    async def _get_client_with_csrf_token(self) -> tuple[httpx.AsyncClient, str]:
        """Get the client with the cached CSRF token.

        This method is used to get the client with the cached CSRF token.
        It is used to avoid the overhead of fetching a new client with an unauthenticated CSRF token
        for each request.
        """
        async with self._csrf_lock:
            # If cache is empty (first call), populate it
            if not (self._client and self._csrf_token):
                (
                    self._client,
                    self._csrf_token,
                ) = await self._fetch_new_client_with_csrf_token()
            # Hand out the cached client/token for *this* request
            client_to_use, token_to_use = self._client, self._csrf_token
            # Immediately clear the cache so the next caller doesn't reuse this client/token
            self._client = None
            self._csrf_token = None

        # Kick off async prefetch for the *next* request (non-blocking)
        asyncio.create_task(self._prefetch_client_with_csrf_token())
        # Return a dedicated client/token for this request
        return client_to_use, token_to_use

    def _extract_and_update_profile(self, node: Node, idx: int, profile: dict) -> None:
        """Extract the profile data from a node and update the profile dictionary.

        Args:
            node (Node): Pre-parsed node containing the profile information
            idx (int): Index of the node
            profile (dict): The profile dictionary to update in-place
        """
        # Use the selector `label.lbl-title-light` to find the key label
        if not (key_node := node.css_first("label.lbl-title-light")) or not (key := key_node.text(strip=True)):
            raise ProfileParseError(f"Could not parse key for field at index {idx}.")
        # Use the adjacent sibling selector `+` to find value label
        if not (value_node := node.css_first("label.lbl-title-light + label")) or not (
            value := value_node.text(strip=True)
        ):
            raise ProfileParseError(f"Could not parse value for field at index {idx}.")
        logger.debug("Extracted profile field", key=key, value=value, index=idx)
        # If the key is in the map, add it to the profile
        if mapped_key := self.PROFILE_PAGE_HEADER_TO_KEY_MAP.get(key):
            logger.debug("Adding profile field", mapped_key=mapped_key, value=value)
            profile[mapped_key] = value
        else:
            raise ProfileParseError(
                f"Unknown key: '{key}' in the profile page. The webpage might have changed.",
            )

    async def prefetch_client_with_csrf_token(self) -> None:
        """Public method to prefetch a new client with an unauthenticated CSRF token.

        This method is used to prefetch a new client with an unauthenticated CSRF token.
        It is used to avoid the overhead of fetching a new client with an unauthenticated CSRF token
        for each request.
        """
        await self._prefetch_client_with_csrf_token()

    async def close_client(self) -> None:
        """Public method to close the internal client if it exists.

        This method is used to close the internal client if it exists.
        It is used to avoid the overhead of closing the client for each request.
        """
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def get_profile_information(
        self,
        client: httpx.AsyncClient,
        username: str,
    ) -> dict[str, Any]:
        """Get the profile information of the user.

        Args:
            client (httpx.Client): The HTTP client to use for making requests.
            username (str): The username of the user, usually their PRN/email/phone number.

        Returns:
            dict[str, Any]: A dictionary containing the user's profile information.
        """
        # Fetch the profile data from the student profile page
        start_time = time.time()
        logger.info("Fetching profile data from student profile page", username=username)
        profile_url = "https://www.pesuacademy.com/Academy/s/studentProfilePESUAdmin"
        query = {
            "menuId": "670",
            "url": "studentProfilePESUAdmin",
            "controllerMode": "6414",
            "actionType": "5",
            "id": "0",
            "selectedData": "0",
            "_": str(int(datetime.now().timestamp() * 1000)),
        }

        try:
            response = await client.get(profile_url, params=query)
            record_pesu_academy_request("profile", response.status_code)

            # If the status code is not 200, raise an exception because the profile page is not accessible
            if response.status_code != 200:
                raise ProfileFetchError(
                    f"Failed to fetch student profile page from PESU Academy for user={username}.",
                )
            logger.debug("Student profile page fetched successfully", username=username)
        except Exception as e:
            logger.error("Failed to fetch profile page", username=username, error=str(e))
            raise

        # Parse the response text
        soup = await asyncio.to_thread(HTMLParser, response.text)
        # Get the details container and its nodes where the profile information is stored
        if (
            not (details_container := soup.css_first("div.elem-info-wrapper"))
            or not (details_nodes := details_container.css("div.form-group"))
            or len(details_nodes) < 7
        ):
            raise ProfileParseError(
                f"Failed to parse student profile page from PESU Academy for user={username}."
                "The webpage might have changed.",
            )

        # Extract the profile information from the profile page
        profile: dict[str, Any] = {}
        for i in range(7):
            self._extract_and_update_profile(details_nodes[i], i, profile)

        # Get the email and phone number from the profile page
        if (
            (email_node := soup.css_first("#updateMail"))
            and (email_value := email_node.attributes.get("value"))
            and isinstance(email_value, str)
        ):
            profile["email"] = email_value.strip()

        if (
            (phone_node := soup.css_first("#updateContact"))
            and (phone_value := phone_node.attributes.get("value"))
            and isinstance(phone_value, str)
        ):
            profile["phone"] = phone_value.strip()

        # If username starts with PES1, then they are from RR campus, else if it is PES2, then EC campus
        if profile.get("prn") and (campus_code_match := re.match(r"PES(\d)", profile["prn"])):
            campus_code = campus_code_match.group(1)
            profile["campus_code"] = int(campus_code)
            if campus_code == "1":
                profile["campus"] = "RR"
            elif campus_code == "2":
                profile["campus"] = "EC"
            else:
                logger.warning(
                    "Unknown campus code detected",
                    campus_code=campus_code,
                    prn=profile.get("prn"),
                    username=username
                )

        # Check if we extracted any profile data
        if not profile:
            raise ProfileParseError(f"No profile data could be extracted for user={username}.")

        # Record metrics for profile fetch duration
        duration = time.time() - start_time
        PROFILE_FETCH_DURATION.observe(duration)

        logger.info("Complete profile information retrieved", username=username, field_count=len(profile))

        return profile

    async def authenticate(
        self,
        username: str,
        password: str,
        profile: bool = False,
        fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """Authenticate the user with the provided username and password.

        Args:
            username (str): The username of the user, usually their PRN/email/phone number.
            password (str): The password of the user.
            profile (bool, optional): Whether to fetch the profile information or not. Defaults to False.
            fields (Optional[list[str]], optional): The fields to fetch from the profile.
            Defaults to None, which means all default fields will be fetched.

        Returns:
            dict[str, Any]: A dictionary containing the authentication status, message,
            and optionally the profile information.
        """
        # Default fields to fetch if fields is not provided
        fields = self.DEFAULT_FIELDS if fields is None else fields
        # Check if fields is not the default fields and enable field filtering
        field_filtering = fields != self.DEFAULT_FIELDS

        logger.info(
            "Starting authentication with PESU Academy",
            username=username,
            profile=profile,
            field_count=len(fields) if fields else 0,
            field_filtering=field_filtering
        )

        # Get a pre-fetched csrf token and client
        client, csrf_token = await self._get_client_with_csrf_token()
        logger.debug("Using cached CSRF token", username=username)
        record_csrf_operation("cache_hit")

        # Prepare the login data for auth call
        data = {
            "_csrf": csrf_token,
            "j_username": username,
            "j_password": password,
        }

        logger.debug("Attempting user authentication", username=username)
        # Make a post request to authenticate the user
        auth_url = settings.pesu_academy_auth_url
        response = await client.post(auth_url, data=data)
        record_pesu_academy_request("auth", response.status_code)
        soup = await asyncio.to_thread(HTMLParser, response.text)
        logger.debug("Authentication response received", username=username)

        # If class login-form is present, login failed
        if soup.css_first("div.login-form"):
            # Log the error and return the error message
            raise AuthenticationError(
                f"Invalid username or password, or user does not exist for user={username}.",
            )

        # If the user is successfully authenticated
        logger.info("Login successful", username=username)
        status = True
        # Get the newly authenticated csrf token
        if csrf_node := soup.css_first("meta[name='csrf-token']"):
            csrf_token = csrf_node.attributes.get("content")
            logger.debug("Authenticated CSRF token obtained", username=username, token_length=len(csrf_token))
        else:
            raise CSRFTokenError(
                f"CSRF token not found in the post-authentication response for user={username}.",
            )

        result = {"status": status, "message": "Login successful."}

        if profile:
            logger.info("Profile data requested, fetching profile data", username=username)
            # Fetch the profile information
            result["profile"] = await self.get_profile_information(client, username)
            # Filter the fields if field filtering is enabled
            if field_filtering:
                result["profile"] = {key: value for key, value in result["profile"].items() if key in fields}
                logger.info(
                    "Field filtering applied to profile data",
                    username=username,
                    filtered_fields=list(result["profile"].keys())
                )

        logger.info("Authentication process completed successfully", username=username)

        # Close the client and return the result
        await client.aclose()
        return result
