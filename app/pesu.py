import logging
import re
import traceback
from datetime import datetime
from typing import Any

import httpx
from selectolax.parser import HTMLParser
from app.constants import PESUAcademyConstants

from app.exceptions.exceptions import ProfileFetchError, CSRFTokenError, AuthenticationError


class PESUAcademy:
    """
    Class to interact with the PESU Academy website.
    """

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

    def get_profile_information(self, client: httpx.Client, username: str) -> dict[str, Any]:
        """
        Get the profile information of the user.

        Args:
            client (httpx.Client): The HTTP client to use for making requests.
            username (str): The username of the user, usually their PRN/email/phone number.

        Returns:
            dict[str, Any]: A dictionary containing the user's profile information.
        """
        try:
            # Fetch the profile data from the student profile page
            logging.info(
                f"Fetching profile data for user={username} from the student profile page..."
            )
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
            response = client.get(profile_url, params=query)
            # If the status code is not 200, raise an exception because the profile page is not accessible
            if response.status_code != 200:
                raise ProfileFetchError()
            logging.debug("Profile data fetched successfully.")
            # Parse the response text
            soup = HTMLParser(response.text)

        except ProfileFetchError:
            logging.exception("Unable to fetch profile data.")
            return {"error": f"Unable to fetch profile data: {traceback.format_exc()}"}
        except Exception:
            # Catch exceptions caused by profile parsing errors
            logging.exception("Error parsing profile from PESUAcademy response.")
            return {"error": f"Unable to parse profile data: {traceback.format_exc()}"}

        profile = dict()
        for div in soup.css("div.form-group")[:7]:
            text = div.text().strip()
            logging.debug(f"Processing profile element: {text}")
            if text.startswith("PESU Id"):
                key = "pesu_id"
                value = text.split()[-1]
            else:
                key, value = text.split(" ", 1)
                key = "_".join(key.split()).lower()
            value = value.strip()
            logging.debug(f"Extracted key: '{key}' with value: '{value}'")
            if key in [
                "name",
                "srn",
                "pesu_id",
                "program",
                "branch",
                "semester",
                "section",
            ]:
                if key == "branch" and (branch_short_code := self.map_branch_to_short_code(value)):
                    profile["branch_short_code"] = branch_short_code
                key = "prn" if key == "pesu_id" else key
                logging.debug(f"Adding key: '{key}', value: '{value}' to profile...")
                profile[key] = value

        # Get the email and phone number from the profile page
        if email_node := soup.css_first("#updateMail"):
            if email_value := email_node.attributes.get("value"):
                email_value = email_value.strip()
            profile["email"] = email_value
        if phone_node := soup.css_first("#updateContact"):
            if phone_value := phone_node.attributes.get("value"):
                phone_value = phone_value.strip()
            profile["phone"] = phone_value

        # if username starts with PES1, then they are from RR campus, else if it is PES2, then EC campus
        if campus_code_match := re.match(r"PES(\d)", profile["prn"]):
            campus_code = campus_code_match.group(1)
            profile["campus_code"] = int(campus_code)
            profile["campus"] = "RR" if campus_code == "1" else "EC"

        logging.info(f"Complete profile information retrieved for user={username}: {profile}")
        return profile

    def authenticate(
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
        # Create a new client session
        client = httpx.Client(follow_redirects=True, timeout=httpx.Timeout(10.0))
        # Default fields to fetch if fields is not provided
        fields = PESUAcademyConstants.DEFAULT_FIELDS if fields is None else fields
        # check if fields is not the default fields and enable field filtering
        field_filtering = fields != PESUAcademyConstants.DEFAULT_FIELDS

        logging.info(
            f"Connecting to PESU Academy with user={username}, profile={profile}, fields={fields} ..."
        )
        try:
            # Get the initial csrf token assigned to the user session when the home page is loaded
            logging.debug("Fetching CSRF token from the home page...")
            home_url = "https://www.pesuacademy.com/Academy/"
            response = client.get(home_url)
            soup = HTMLParser(response.text)
            # extract the csrf token from the meta tag
            if csrf_node := soup.css_first("meta[name='csrf-token']"):
                csrf_token = csrf_node.attributes.get("content")
                logging.debug(f"CSRF token fetched: {csrf_token}")
            else:
                raise CSRFTokenError("CSRF token not found in the response.")
        except CSRFTokenError as err:
            # Log the error and return the error message
            logging.exception("Unable to fetch csrf token.")
            client.close()
            return {
                "status": False,
                "message": f"Unable to fetch csrf token. {str(err)}",
            }

        # Prepare the login data for auth call
        data = {
            "_csrf": csrf_token,
            "j_username": username,
            "j_password": password,
        }

        try:
            logging.debug("Attempting to authenticate user...")
            # Make a post request to authenticate the user
            auth_url = "https://www.pesuacademy.com/Academy/j_spring_security_check"
            response = client.post(auth_url, data=data)
            soup = HTMLParser(response.text)
            logging.debug("Authentication response received.")
        except Exception:
            # Log the error and return the error message
            logging.exception("Unable to authenticate.")
            client.close()
            return {
                "status": False,
                "message": str(AuthenticationError()),
            }

        # If class login-form is present, login failed
        if soup.css_first("div.login-form"):
            # Log the error and return the error message
            logging.error("Login unsuccessful. Invalid username or password.")
            client.close()
            return {"status": False, "message": str(AuthenticationError())}

        # If the user is successfully authenticated
        logging.info(f"Login successful for user={username}.")
        status = True
        # Get the newly authenticated csrf token
        if csrf_node := soup.css_first("meta[name='csrf-token']"):
            csrf_token = csrf_node.attributes.get("content")
            logging.debug(f"Authenticated CSRF token: {csrf_token}")
        else:
            logging.exception("CSRF token not found in the authenticated response.")

        result = {"status": status, "message": "Login successful."}

        if profile:
            logging.info(f"Profile data requested for user={username}. Fetching profile data...")
            # Fetch the profile information
            result["profile"] = self.get_profile_information(client, username)
            # Filter the fields if field filtering is enabled
            if field_filtering:
                result["profile"] = {
                    key: value for key, value in result["profile"].items() if key in fields
                }
                logging.info(
                    f"Field filtering enabled. Filtered profile data for user={username}: {result['profile']}"
                )

        logging.info(f"Authentication process for user={username} completed successfully.")
        # Close the client session and return the result
        client.close()
        return result
