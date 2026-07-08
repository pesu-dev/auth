"""PESUAcademy class that serves as an interface to the PESU Academy website."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Literal, get_args

import httpx

from app.exceptions.authentication import AuthenticationError

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
}


class PESUAcademy:
    """Class to interact with the PESU Academy server.

    This class provides methods to authenticate users.
    """

    DEFAULT_FIELDS: list[str] = list(get_args(ProfileField))

    def __init__(self) -> None:
        """Initialize the PESUAcademy class."""
        pass

    def _parse_sslc_name(self, res_data: object) -> str | None:
        """Parse nameAsInSSLC from the ISA marks response JSON."""
        if not isinstance(res_data, dict):
            return None
        for marks in res_data.values():
            if not isinstance(marks, list):
                continue
            for mark in marks:
                if not isinstance(mark, dict):
                    continue
                name_sslc = mark.get("NameAsInSSLC")
                if name_sslc and name_sslc.strip():
                    return name_sslc.strip()
        return None

    async def _fetch_name_as_in_sslc(self, client: httpx.AsyncClient, token: str, user_id: str) -> str | None:
        """Fetch the official name (nameAsInSSLC) from ISA results."""
        dispatcher_url = "https://www.pesuacademy.com/MAcademy/mobile/dispatcher"
        headers = {"mobileappauthenticationtoken": token}

        # 1. Fetch ISA semesters
        sem_payload = {
            "action": "6",
            "mode": "5",
            "userId": user_id,
            "randomNum": "0.5",
            "whichObjectId": "clickHome_footer_myresults",
            "title": "ISA Results",
            "serverMode": "0",
            "redirectValue": "redirect:/a/ad",
        }
        try:
            sem_resp = await client.post(dispatcher_url, data=sem_payload, headers=headers)
            if sem_resp.status_code != 200:
                return None
            sem_data = sem_resp.json()
            if isinstance(sem_data, str):
                sem_data = json.loads(sem_data)
            if not isinstance(sem_data, list) or len(sem_data) == 0:
                return None

            # Get the first/current semester
            semester = sem_data[0]
            batch_class_id = semester.get("BatchClassId")
            class_batch_section_id = semester.get("ClassBatchSectionId")
            if batch_class_id is None or class_batch_section_id is None:
                return None

            # 2. Fetch ISA results for that semester
            results_payload = {
                "action": "6",
                "mode": "9",
                "userId": user_id,
                "randomNum": "0.5",
                "batchClassId": str(batch_class_id),
                "classBatchSectionId": str(class_batch_section_id),
                "fetchId": f"{batch_class_id}-{class_batch_section_id}",
            }
            res_resp = await client.post(dispatcher_url, data=results_payload, headers=headers)
            if res_resp.status_code != 200:
                return None
            res_data = res_resp.json()
            if isinstance(res_data, str):
                res_data = json.loads(res_data)

            return self._parse_sslc_name(res_data)
        except Exception:
            pass
        return None

    def _map_data(
        self,
        data: dict[str, Any],
        username: str,
        profile: bool,
        know_your_class_and_section: bool,
        fields: list[str],
        field_filtering: bool,
        name_sslc: str | None = None,
    ) -> dict[str, Any]:
        """Map the profile and class/section data from the response JSON."""
        prn = data.get("loginId")
        srn = data.get("departmentId") or username
        campus_code = None
        campus = None
        if prn and (campus_code_match := re.match(r"PES(\d)", prn)):
            campus_code = int(campus_code_match.group(1))
            if campus_code == 1:
                campus = "RR"
            elif campus_code == 2:
                campus = "EC"

        semester_val = _get_semester_from_class(data.get("className"), data.get("batchClass"))
        program_raw = data.get("program")
        program = PROGRAM_MAPPING.get(program_raw, program_raw)
        branch_raw = data.get("branch")
        branch = BRANCH_MAPPING.get(branch_raw, branch_raw)

        # Prepare the authentication result dictionary
        result = {"status": True, "message": "Login successful."}

        # Fetch the profile information if profile details are requested
        name = name_sslc or data.get("name")
        if profile:
            profile_dict = {
                "name": name,
                "prn": prn,
                "srn": srn,
                "program": program,
                "branch": branch,
                "semester": semester_val,
                "section": data.get("sectionName"),
                "email": data.get("email"),
                "phone": data.get("phone"),
                "campusCode": campus_code,
                "campus": campus,
            }
            # Filter the fields if field filtering is enabled
            if field_filtering:
                profile_dict = {k: v for k, v in profile_dict.items() if k in fields}
            result["profile"] = profile_dict

        # Fetch the "Know Your Class and Section" data if requested
        if know_your_class_and_section:
            kycas_dict = {
                "prn": prn,
                "srn": srn,
                "name": name,
                "semester": semester_val,
                "section": f"Section {data.get('sectionName')}" if data.get("sectionName") else None,
                "cycle": "NA",
                "department": data.get("branch"),
                "branch": data.get("branch"),
                "instituteName": "PES University",
            }
            # Filter the fields if field filtering is enabled
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
        login_url = "https://www.pesuacademy.com/MAcademy/j_spring_security_check"
        payload = {
            "j_username": username,
            "j_password": password,
            "j_mobile": "MOBILE",
            "j_mobileApp": "YES",
            "j_social": "NO",
            "j_appId": "1",
            "action": "0",
            "mode": "0",
            "whichObjectId": "loginSubmitButton",
            "randomNum": 0.5,
        }

        # Make a post request to authenticate the user
        async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
            try:
                response = await client.post(login_url, data=payload)
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

            # If the response does not indicate success, raise an AuthenticationError
            if not isinstance(data, dict) or data.get("login") != "SUCCESS":
                error_msg = data.get("errorMessage") if isinstance(data, dict) else None
                raise AuthenticationError(
                    error_msg or f"Invalid username or password, or user does not exist for user={username}."
                )

            # If the user is successfully authenticated
            logging.info(f"Login successful for user={username}.")

            # Return early if no profile or class section details are requested
            if not profile and not know_your_class_and_section:
                return {"status": True, "message": "Login successful."}

            token = response.headers.get("mobileappauthenticationtoken") or ""
            user_id = str(data.get("userId") or "")
            name_sslc = None
            if token and user_id:
                name_sslc = await self._fetch_name_as_in_sslc(client, token, user_id)

            # Map the parsed response JSON to return format
            return self._map_data(
                data=data,
                username=username,
                profile=profile,
                know_your_class_and_section=know_your_class_and_section,
                fields=fields,
                field_filtering=field_filtering,
                name_sslc=name_sslc,
            )
