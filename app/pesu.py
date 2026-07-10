"""PESUAcademy class that serves as an interface to the PESU Academy Mobile API."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Literal, get_args

import httpx

from app.exceptions.authentication import AuthenticationError

# used to to generate list of default field names
ProfileField = Literal[
    "name",
    "prn",
    "srn",
    "program",
    "branch",
    "semester",
    "section",
    "email",
    "phone",
    "campusCode",
    "campus",
    "cycle",
    "department",
    "instituteName",
]

"""
Extract semester format (e.g. 'Sem-2') from class name or batch class.
Tries two possible source strings (class_name, then batch_class) and attempts
three regex patterns in order of specificity:
    1.Matches things like "Semester-3" or "Sem3" → extracts 3.
    2.Matches things like "3rd-Sem" → extracts 3.
    3.Falls back to just grabbing any standalone number in the string.
"""


def _get_semester_from_class(class_name: str | None, batch_class: str | None) -> str | None:
    """Extract semester format (e.g. 'Sem-2') from class name or batch class."""
    for val in (class_name, batch_class):
        if not val:
            continue
        if m := re.search(r"Sem(?:ester)?[-_ ]?(\d+)", val, re.IGNORECASE):
            return f"Sem-{m.group(1)}"
        if m := re.search(r"(\d+)(?:st|nd|rd|th)?[-_ ]?Sem", val, re.IGNORECASE):
            return f"Sem-{m.group(1)}"
        if m := re.search(r"\b(\d+)\b", val):
            return f"Sem-{m.group(1)}"
    return None


"""
PESU mobile api only returns B.Tech and and just CSE/ECE/EEE so to fix it we use this mapping.
"""
PROGRAM_MAPPING = {
    "B.Tech.": "Bachelor of Technology",
    "B.Tech": "Bachelor of Technology",
    "M.Tech.": "Master of Technology",
    "M.Tech": "Master of Technology",
    "B.Arch.": "Bachelor of Architecture",
    "B.Arch": "Bachelor of Architecture",
    "BBA.": "Bachelor of Business Administration",
    "BBA": "Bachelor of Business Administration",
    "MBA.": "Master of Business Administration",
    "MBA": "Master of Business Administration",
    "BCA": "Bachelor of Computer Applications",
    "BCA.": "Bachelor of Computer Applications",
    "B.Com": "Bachelor of Commerce",
    "B.Com.": "Bachelor of Commerce",
    "MCA": "Master of Computer Applications",
    "MCA.": "Master of Computer Applications",
    "B.DES": "Bachelor of Design",
    "B.DES.": "Bachelor of Design",
}

BRANCH_MAPPING = {
    "Branch:CSE": "Computer Science and Engineering",
    "CSE": "Computer Science and Engineering",
    "Branch:ECE": "Electronics and Communication Engineering",
    "ECE": "Electronics and Communication Engineering",
    "Branch:EEE": "Electrical and Electronics Engineering",
    "EEE": "Electrical and Electronics Engineering",
    "Branch:ME": "Mechanical Engineering",
    "ME": "Mechanical Engineering",
    "Branch:BT": "Biotechnology",
    "BT": "Biotechnology",
    "Branch:CSE(AI-ML)": "Computer Science and Engineering (AI&ML)",
    "CSE(AI-ML)": "Computer Science and Engineering (AI&ML)",
    "Branch:CSE (AI&ML)": "Computer Science and Engineering (AI&ML)",
    "CSE (AI&ML)": "Computer Science and Engineering (AI&ML)",
    "Branch:AIML": "Computer Science and Engineering (AI&ML)",
    "AIML": "Computer Science and Engineering (AI&ML)",
    "Branch:CE": "Civil Engineering",
    "CE": "Civil Engineering",
    "Branch:CV": "Civil Engineering",
    "CV": "Civil Engineering",
}


class PESUAcademy:
    """Class to interact with the PESU Academy server.

    This class provides methods to authenticate users.
    """

    DEFAULT_FIELDS: list[str] = list(get_args(ProfileField))

    def __init__(self) -> None:
        """Initialize the PESUAcademy class."""
        pass

    """
    Example of raw JSON response returned by the PESU Academy dispatcher profile API (action=27, mode=1):
    {
        "MESSAGE": "SUCCESS_Record found Successfully",
        "STUDENT_PHOTO": {
            "userId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
            "loginId": "PES2UG25CS026",
            "status": "A",
            "gender": "Male",
            "email": "student@example.com",
            "mobile": "9876543210",
            "firstName": "JOHN",
            "nameAsInSSLC": "JOHN DOE",
            "programId": 1,
            "branchId": 32,
            "instituteName": "PES University"
        }
    }
    """

    async def _fetch_profile_details(
        self, client: httpx.AsyncClient, token: str, bearer_token: str, user_id: str
    ) -> dict[str, Any] | None:
        """Fetch the profile details from the dispatcher endpoint.

        This returns the actual name (nameAsInSSLC) and the correct PRN (loginId)
        which are accurate compared to the general login response.
        """
        dispatcher_url = "https://www.pesuacademy.com/MAcademy/mobile/dispatcher"
        headers = {
            "mobileappauthenticationtoken": token,
            "authorization": f"Bearer {bearer_token}",
        }
        files = {
            "action": (None, "27"),
            "mode": (None, "1"),
            "userId": (None, user_id),
            "searchUserId": (None, user_id),
        }

        try:
            resp = await client.post(dispatcher_url, headers=headers, files=files)
            if resp.status_code != 200:
                return None
            data = resp.json()
            if isinstance(data, str):
                data = json.loads(data)

            msg = data.get("MESSAGE")
            if msg and "SUCCESS" in msg:
                return data.get("STUDENT_PHOTO", {})
        except Exception:
            # Silently fallback if any network/parsing issue occurs during profile resolution
            pass
        return None

    """
    Example of actual raw JSON response returned by the PESU Academy mobile login API:
    {
      "accessToken": "eyJhbGciOiJSUzI1NiJ9...",
      "mobileJsonObject": {
        "userId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
        "userRoleId": "3",
        "login": "SUCCESS",
        "errorMessage": null,
        "name": "JOHN DOE",
        "photo": "data:image/jpeg;base64,...",
        "phone": "9876543210",
        "email": "student@example.com",
        "program": "B.Tech.",
        "branch": "Branch:CSE",
        "className": "Sem-2, Section A",
        "sectionName": "Section A",
        "loginId": "PES2202501872",
        "departmentId": "0",
        "usertype": "2"
      }
    }
    """

    def _map_data(  # noqa: C901
        self,
        data: dict[str, Any],
        username: str,
        profile: bool,
        know_your_class_and_section: bool,
        fields: list[str],
        field_filtering: bool,
        profile_details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Map the disparate data from both mobile endpoints into a single unified profile schema.

        The PESU Mobile API is fragmented. The initial login response returns a mix of
        basic details, while the dispatcher endpoint provides the actual official records.
        This method merges those two sources (represented by `data` and `profile_details`)
        into the clean, structured format expected by the frontend clients.

        Key transformations include:
        - Resolving the true PRN (Application Number) and SRN (University Roll Number),
          which are returned ambiguously by the backend.
        - Translating raw program/branch codes (e.g., "Branch:CSE(AI-ML)") into readable strings
          ("Computer Science and Engineering (AI&ML)") using internal mappings.
        - Deduce campus information (RR vs EC) dynamically based on the prefix of the PRN.
        - Selectively returning only the fields requested by the client if `field_filtering` is enabled.
        """
        # --- PRN and SRN Resolution ---
        # The new mobile API endpoints are notoriously confusing with identifiers:
        # 1. The login endpoint (`data`) returns the Application Number (PRN) under the
        #    key `loginId` (e.g., PES2202501872).
        # 2. The dispatcher endpoint (`profile_details`) returns the actual University SRN
        #    under the exact same `loginId` key (e.g., PES2UG25CS026).
        # We must carefully map these to our explicit `prn` and `srn` keys to prevent downstream bugs.
        prn = data.get("loginId")
        srn = (profile_details.get("loginId") if profile_details else None) or data.get("departmentId") or username
        campus_code = None
        campus = None

        # Deduce campus code and campus name prefix from PRN (e.g. PES1... or PES2...)
        if prn and (campus_code_match := re.match(r"PES(\d)", prn)):
            campus_code = int(campus_code_match.group(1))
            if campus_code == 1:
                campus = "RR"
            elif campus_code == 2:
                campus = "EC"

        # Extract and normalize semester structure
        semester_val = _get_semester_from_class(data.get("className"), data.get("batchClass"))
        program_raw = data.get("program")
        program = PROGRAM_MAPPING.get(program_raw, program_raw)
        branch_raw = data.get("branch")
        branch = BRANCH_MAPPING.get(branch_raw, branch_raw)

        # Prepare base authentication response structure
        result = {"status": True, "message": "Login successful."}

        # Build and map profile information block if requested
        name = (profile_details.get("nameAsInSSLC") if profile_details else None) or data.get("name")
        if profile:
            profile_dict = {
                "name": name,
                "prn": prn,
                "srn": srn,
                "program": program,
                "branch": branch,
                "semester": semester_val,
                "section": data.get("sectionName"),
                "email": (profile_details.get("email") if profile_details else None) or data.get("email"),
                "phone": (profile_details.get("mobile") if profile_details else None) or data.get("phone"),
                "campusCode": campus_code,
                "campus": campus,
            }
            # Filter profile dictionary keys if field filtering is active
            if field_filtering:
                profile_dict = {k: v for k, v in profile_dict.items() if k in fields}
            result["profile"] = profile_dict

        # Build and map Class and Section block if requested
        if know_your_class_and_section:
            # Deduce missing information originally provided by the web scraping API
            kycas_branch = data.get("branch", "").replace("Branch:", "")
            kycas_inst = "PES University (Electronic City)" if campus == "EC" else "PES University (Ring Road Campus)"

            kycas_cycle = "NA"
            kycas_dept = branch
            if semester_val in ("Sem-1", "Sem-2"):
                kycas_dept = f"S & H - PESU ({campus} Campus)"
                section_letter = str(data.get("sectionName", "")).replace("Section ", "").strip()

                if section_letter:
                    is_a_to_n = section_letter[0].upper() <= "N"
                    if semester_val == "Sem-1":
                        kycas_cycle = "Chemistry Cycle" if is_a_to_n else "Physics Cycle"
                    else:  # Sem-2
                        kycas_cycle = "Physics Cycle" if is_a_to_n else "Chemistry Cycle"

            kycas_dict = {
                "prn": prn,
                "srn": srn,
                "name": name,
                "semester": semester_val,
                "section": data.get("sectionName"),
                "cycle": kycas_cycle,
                "department": kycas_dept,
                "branch": kycas_branch,
                "instituteName": kycas_inst,
            }
            # Filter class and section dictionary keys if field filtering is active
            if field_filtering:
                kycas_dict = {k: v for k, v in kycas_dict.items() if k in fields}
            result["knowYourClassAndSection"] = kycas_dict

        return result

    async def authenticate(
        self,
        username: str,
        password: str,
        profile: bool = False,
        know_your_class_and_section: bool = False,
        fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """Authenticate the user with the provided username and password.

        Args:
            username (str): The username of the user, usually their PRN/email/phone number.
            password (str): The password of the user.
            profile (bool, optional): Whether to fetch the profile information or not. Defaults to False.
            know_your_class_and_section (bool, optional): Whether to fetch from the
                "Know Your Class and Section" endpoint or not. Defaults to False.
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

        logging.info(
            f"Connecting to PESU Academy mobile API with user={username}, profile={profile}, fields={fields} ...",
        )

        # Prepare the payload for mobile login API
        login_url = "https://www.pesuacademy.com/MAcademy/mobile/mobilelogin/auth"
        files = {
            "userName": (None, username),
            "password": (None, password),
            "j_appId": (None, "YES"),
            "instId": (None, "1,6,7,14"),
        }

        # Make a post request to authenticate the user
        async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
            try:
                response = await client.post(login_url, files=files)
            except Exception as e:
                raise AuthenticationError(f"Connection failed: {str(e)}")

            # Check if the response status code is 200
            if response.status_code != 200:
                raise AuthenticationError(
                    f"Authentication failed: Server returned status code {response.status_code}",
                )

            # Parse the response JSON
            try:
                data = response.json()
            except Exception:
                raise AuthenticationError("Authentication failed: Invalid JSON response from server")

            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except Exception:
                    raise AuthenticationError("Authentication failed: Invalid nested JSON response")

            # Validate the mobileJsonObject structure
            mobile_obj = data.get("mobileJsonObject") if isinstance(data, dict) else None

            if not isinstance(mobile_obj, dict) or mobile_obj.get("login") != "SUCCESS":
                error_msg = mobile_obj.get("errorMessage") if isinstance(mobile_obj, dict) else None
                raise AuthenticationError(
                    error_msg or f"Invalid username or password, or user does not exist for user={username}."
                )

            # If the user is successfully authenticated
            logging.info(f"Login successful for user={username}.")

            # Return early if no profile or class section details are requested
            if not profile and not know_your_class_and_section:
                return {"status": True, "message": "Login successful."}

            token = response.headers.get("mobileappauthenticationtoken") or ""
            bearer_token = data.get("accessToken") or mobile_obj.get("accessToken") or ""
            user_id = str(mobile_obj.get("userId") or "")

            profile_details = None
            if token and user_id and bearer_token:
                profile_details = await self._fetch_profile_details(client, token, bearer_token, user_id)

            # Map the parsed response JSON to return format
            return self._map_data(
                data=mobile_obj,
                username=username,
                profile=profile,
                know_your_class_and_section=know_your_class_and_section,
                fields=fields,
                field_filtering=field_filtering,
                profile_details=profile_details,
            )
