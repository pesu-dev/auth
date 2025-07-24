import asyncio
import logging
import re
from datetime import datetime
from typing import Any

import httpx
from selectolax.parser import HTMLParser, Node
from app.constants import PESUAcademyConstants

from app.exceptions.authentication import (
    ProfileFetchError,
    ProfileParseError,
    CSRFTokenError,
    AuthenticationError,
)


class PESUAcademy:
    """
    Class to interact with the PESU Academy website.
    """

    PROFILE_PAGE_HEADER_TO_KEY_MAP = {
        "Name": "name",
        "PESU Id": "prn",
        "SRN": "srn",
        "Program": "program",
        "Branch": "branch",
        "Semester": "semester",
        "Section": "section",
    }

    def __init__(self):
        self._csrf_token: str | None = None
        self._client: httpx.AsyncClient | None = None
        self._csrf_lock = asyncio.Lock()

    @staticmethod
    async def _fetch_new_client_with_csrf_token() -> tuple[httpx.AsyncClient, str]:
        """Fetch a fresh client with an unauthenticated CSRF token from PESU Academy."""
        logging.info("Fetching a new client with an unauthenticated CSRF token...")
        # Create a new client
        client = httpx.AsyncClient(follow_redirects=True, timeout=10.0)
        # Fetch the CSRF token
        resp = await client.get("https://www.pesuacademy.com/Academy/")
        soup = await asyncio.to_thread(HTMLParser, resp.text)
        if node := soup.css_first("meta[name='csrf-token']"):
            csrf_token = node.attributes["content"]
            logging.info(f"Fetched CSRF token: {csrf_token}")
            return client, csrf_token
        else:
            raise CSRFTokenError("CSRF token not found in the pre-authentication response.")

    async def _prefetch_client_with_csrf_token(self):
        """Prefetch a new client with an unauthenticated CSRF token."""
        logging.info("Prefetching a new client with an unauthenticated CSRF token...")
        client, token = await self._fetch_new_client_with_csrf_token()
        async with self._csrf_lock:
            # Close old cached client (if any) to avoid leaks
            if self._client is not None:
                await self._client.aclose()
            # Store the new cached client/token
            self._client = client
            self._csrf_token = token
        logging.info("Cache refreshed with new unauthenticated CSRF token.")

    async def _get_client_with_csrf_token(self) -> tuple[httpx.AsyncClient, str]:
        """Get the client with the cached CSRF token."""
        async with self._csrf_lock:
            # If cache is empty (first call), populate it
            if not (self._client and self._csrf_token):
                self._client, self._csrf_token = await self._fetch_new_client_with_csrf_token()
            # Hand out the cached client/token for *this* request
            client_to_use, token_to_use = self._client, self._csrf_token
            # Immediately clear the cache so the next caller doesn't reuse this client/token
            self._client = None
            self._csrf_token = None

        # Kick off async prefetch for the *next* request (non-blocking)
        asyncio.create_task(self._prefetch_client_with_csrf_token())
        # Return a dedicated client/token for this request
        return client_to_use, token_to_use

    async def _extract_and_update_profile(self, node: Node, idx: int, profile: dict):
        """
        Extracts the profile data from a node and updates the profile dictionary.

        Args:
            node (Node): Pre-parsed node containing the profile information
            idx (int): Index of the node
            profile (dict): The profile dictionary to update in-place
        """

        def parse_and_update():
            # Use the selector `label.lbl-title-light` to find the key label
            if not (key_node := node.css_first("label.lbl-title-light")) or not (
                key := key_node.text(strip=True)
            ):
                raise ProfileParseError(f"Could not parse key for field at index {idx}.")
            # Use the adjacent sibling selector `+` to find value label
            if not (value_node := node.css_first("label.lbl-title-light + label")) or not (
                value := value_node.text(strip=True)
            ):
                raise ProfileParseError(f"Could not parse value for field at index {idx}.")
            logging.debug(f"Extracted key: '{key}' with value: '{value}' at index {idx}.")
            # If the key is in the map, add it to the profile
            if mapped_key := self.PROFILE_PAGE_HEADER_TO_KEY_MAP.get(key):
                logging.debug(f"Adding key: '{mapped_key}', value: '{value}' to profile...")
                profile[mapped_key] = value
                if mapped_key == "branch" and (
                    branch_short_code := self.map_branch_to_short_code(value)
                ):
                    profile["branch_short_code"] = branch_short_code
                    logging.debug(
                        f"Adding key: 'branch_short_code', value: '{branch_short_code}' to profile..."
                    )
            else:
                raise ProfileParseError(
                    f"Unknown key: '{key}' in the profile page. The webpage might have changed."
                )

        await asyncio.to_thread(parse_and_update)

    async def prefetch_client_with_csrf_token(self):
        """Public method to prefetch a new client with an unauthenticated CSRF token."""
        await self._prefetch_client_with_csrf_token()

    async def close_client(self):
        """Public method to close the internal client if it exists."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @staticmethod
    def map_branch_to_short_code(branch: str) -> str | None:
        """
        Map the branch name to its short code.

        Args:
            branch (str): The full name of the branch.

        Returns:
            Optional[str]: The short code for the branch if it exists, otherwise None.
        """
        logging.warning(
            "Branch short code mapping will be deprecated in future versions. If you require acronyms, please do it application-side."
        )
        return PESUAcademyConstants.BRANCH_SHORT_CODES.get(branch)

    async def get_profile_information(
        self, client: httpx.AsyncClient, username: str
    ) -> dict[str, Any]:
        """
        Get the profile information of the user.

        Args:
            client (httpx.Client): The HTTP client to use for making requests.
            username (str): The username of the user, usually their PRN/email/phone number.

        Returns:
            dict[str, Any]: A dictionary containing the user's profile information.
        """
        # Fetch the profile data from the student profile page
        logging.info(f"Fetching profile data for user={username} from the student profile page...")
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
        response = await client.get(profile_url, params=query)
        # If the status code is not 200, raise an exception because the profile page is not accessible
        if response.status_code != 200:
            raise ProfileFetchError(
                f"Failed to fetch student profile page from PESU Academy for user={username}."
            )
        logging.debug("Student profile page fetched successfully.")

        # Parse the response text
        soup = await asyncio.to_thread(HTMLParser, response.text)
        # Get the details container and its nodes where the profile information is stored
        if (
            not (details_container := soup.css_first("div.elem-info-wrapper"))
            or not (details_nodes := details_container.css("div.form-group"))
            or len(details_nodes) < 7
        ):
            raise ProfileParseError(
                f"Failed to parse student profile page from PESU Academy for user={username}. The webpage might have changed."
            )

        # Extract the profile information from the profile page
        profile: dict[str, Any] = {}
        tasks = [self._extract_and_update_profile(details_nodes[i], i, profile) for i in range(7)]
        await asyncio.gather(*tasks)

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
                logging.warning(
                    f"Unknown campus code: {campus_code} parsed from PRN={profile['prn']} for user={username}"
                )

        # Check if we extracted any profile data
        if not profile:
            raise ProfileParseError(f"No profile data could be extracted for user={username}.")
        logging.info(f"Complete profile information retrieved for user={username}: {profile}.")

        return profile

    async def authenticate(
        self,
        username: str,
        password: str,
        profile: bool = False,
        fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Authenticate the user with the provided username and password.

        Args:
            username (str): The username of the user, usually their PRN/email/phone number.
            password (str): The password of the user.
            profile (bool, optional): Whether to fetch the profile information or not. Defaults to False.
            fields (Optional[list[str]], optional): The fields to fetch from the profile. Defaults to None, which means all default fields will be fetched.

        Returns:
            dict[str, Any]: A dictionary containing the authentication status, message, and optionally the profile information.
        """
        # Default fields to fetch if fields is not provided
        fields = PESUAcademyConstants.DEFAULT_FIELDS if fields is None else fields
        # Check if fields is not the default fields and enable field filtering
        field_filtering = fields != PESUAcademyConstants.DEFAULT_FIELDS

        logging.info(
            f"Connecting to PESU Academy with user={username}, profile={profile}, fields={fields} ..."
        )

        # Get a pre-fetched csrf token and client
        client, csrf_token = await self._get_client_with_csrf_token()
        logging.debug(f"Using cached CSRF token for user={username}.")

        # Prepare the login data for auth call
        data = {
            "_csrf": csrf_token,
            "j_username": username,
            "j_password": password,
        }

        logging.debug("Attempting to authenticate user...")
        # Make a post request to authenticate the user
        auth_url = "https://www.pesuacademy.com/Academy/j_spring_security_check"
        response = await client.post(auth_url, data=data)
        soup = await asyncio.to_thread(HTMLParser, response.text)
        logging.debug("Authentication response received.")

        # If class login-form is present, login failed
        if soup.css_first("div.login-form"):
            # Log the error and return the error message
            raise AuthenticationError(
                f"Invalid username or password, or user does not exist for user={username}."
            )

        # If the user is successfully authenticated
        logging.info(f"Login successful for user={username}.")
        status = True
        # Get the newly authenticated csrf token
        if csrf_node := soup.css_first("meta[name='csrf-token']"):
            csrf_token = csrf_node.attributes.get("content")
            logging.debug(f"Authenticated CSRF token: {csrf_token}")
        else:
            raise CSRFTokenError(
                f"CSRF token not found in the post-authentication response for user={username}."
            )

        result = {"status": status, "message": "Login successful."}

        if profile:
            logging.info(f"Profile data requested for user={username}. Fetching profile data...")
            # Fetch the profile information
            result["profile"] = await self.get_profile_information(client, username)
            # Filter the fields if field filtering is enabled
            if field_filtering:
                result["profile"] = {
                    key: value for key, value in result["profile"].items() if key in fields
                }
                logging.info(
                    f"Field filtering enabled. Filtered profile data for user={username}: {result['profile']}"
                )

        logging.info(f"Authentication process for user={username} completed successfully.")

        # Close the client and return the result
        await client.aclose()
        return result
