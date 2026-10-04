"""PESUAcademy class that serves as an interface to the PESU Academy mobile API."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, Literal, get_args

import httpx2
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from app.exceptions.authentication import (
    AuthenticationError,
    ProfileFetchError,
    ProfileParseError,
    UpstreamError,
)
from app.metrics.collector import (
    HTTP_CLIENTS,
    PROFILE_FIELD_FILTERING,
    PROFILE_PARSE_ERRORS,
    UPSTREAM_LATENCY,
    UPSTREAM_REQUESTS,
    UPSTREAM_RESPONSES,
    MetricsCollector,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping

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
]

# The mobile app's API is undocumented. Every value below was read off the app's own traffic and can
# change with an app release, without notice; when logins or profiles start failing, start here.
LOGIN_URL = "https://www.pesuacademy.com/MAcademy/mobile/mobilelogin/auth"
DISPATCHER_URL = "https://www.pesuacademy.com/MAcademy/mobile/dispatcher"
# Sent on both calls because the app sends it; it is what marks the traffic as the mobile client's
MOBILE_HEADERS = {"X-Client-Type": "MOBILE"}
# Fixed by the app. instId lists the PES institutes a login is tried against, so a student of any of
# them can sign in without saying which one they belong to.
LOGIN_FORM = {"j_appId": "YES", "instId": "1,6,7,14"}
# The app's "My Profile" screen. A dispatcher call names a screen rather than a URL path.
PROFILE_FORM = {"action": "27", "mode": "1", "menuId": "11172"}
UPSTREAM_TIMEOUT_SECONDS = 10.0

CAMPUS_NAMES = {"1": "RR", "2": "EC"}
# The mobile API only returns the program's abbreviation, but the API has always returned the full
# name, which is what callers display. Keys are normalised by _normalise_program. "B.Tech." has been
# checked against the full name the web portal shows; the rest are the standard expansions.
PROGRAM_NAMES = {
    "B.TECH": "Bachelor of Technology",
    "M.TECH": "Master of Technology",
    "B.ARCH": "Bachelor of Architecture",
    "M.ARCH": "Master of Architecture",
    "B.DES": "Bachelor of Design",
    "BBA": "Bachelor of Business Administration",
    "MBA": "Master of Business Administration",
    "BCA": "Bachelor of Computer Applications",
    "MCA": "Master of Computer Applications",
    "B.COM": "Bachelor of Commerce",
    "M.COM": "Master of Commerce",
    "B.SC": "Bachelor of Science",
    "M.SC": "Master of Science",
    "B.PHARM": "Bachelor of Pharmacy",
    "M.PHARM": "Master of Pharmacy",
    "PHARM.D": "Doctor of Pharmacy",
    "PH.D": "Doctor of Philosophy",
}
# What upstream sends for a value it does not have. "NA" is what the web portal showed for a student
# with no current class; it is a placeholder, not a value, so it is treated like a missing one.
MISSING_VALUES = frozenset({"", "NA"})
# A PRN is "PES", the campus digit, the admission year and a serial number, all digits. An SRN carries
# letters (PES2UG25CS026), so this tells the two apart when upstream puts either under "loginId".
PRN_PATTERN = re.compile(r"PES\d{10}")
CAMPUS_CODE_PATTERN = re.compile(r"PES(\d)")


# Strong references to in-flight client closes. A close that outlives the coroutine which asked
# for it (see _close_client_quietly) would otherwise be a bare task, free to be garbage collected
# mid-flight. See https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task
_CLOSE_TASKS: set[asyncio.Task[None]] = set()


class _UpstreamModel(BaseModel):
    """Base for the response shapes read from PESU Academy.

    Only the fields this service returns are declared; everything else is dropped as the response is
    parsed. Those responses also carry the student's photo, date of birth, addresses, marks and their
    parents' contact details. Never holding them means no log line, exception or repr can leak them.
    """

    model_config = ConfigDict(extra="ignore", coerce_numbers_to_str=True)

    @field_validator("*", mode="before")
    @classmethod
    def _placeholder_to_none(cls, value: Any) -> Any:  # noqa: ANN401
        """Treat a blank or placeholder string as a missing value.

        Upstream sends "" (and the web portal sent "NA") as often as null for a value it does not
        have, and all of them mean the same thing to a caller: null, not a string.

        Args:
            value (Any): The raw value from the response.

        Returns:
            Any: The value stripped, or None if it was blank or a placeholder.
        """
        if isinstance(value, str):
            value = value.strip()
            return None if value in MISSING_VALUES else value
        return value


class _LoginUser(_UpstreamModel):
    """The student as described by the login response's `mobileJsonObject`."""

    login: str | None = None
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    program: str | None = None
    class_name: str | None = Field(None, alias="className")
    section_name: str | None = Field(None, alias="sectionName")
    login_id: str | None = Field(None, alias="loginId")


class _LoginResponse(_UpstreamModel):
    """The login response: the student, and the token the profile call needs."""

    user: _LoginUser = Field(alias="mobileJsonObject")
    # repr=False so the bearer token cannot reach a log through the model's repr
    access_token: str | None = Field(None, alias="accessToken", repr=False)


class _StudentInfo(_UpstreamModel):
    """The student as described by the profile response's `STUDENT_INFO`."""

    login_id: str | None = Field(None, alias="LoginId")
    srn: str | None = Field(None, alias="SRN")
    name: str | None = Field(None, alias="NameAsInSSLC")
    email: str | None = Field(None, alias="Email")
    mobile: str | None = Field(None, alias="Mobile")
    program: str | None = Field(None, alias="ProgramAbbreviation")
    branch: str | None = Field(None, alias="Branch")
    class_name: str | None = Field(None, alias="ClassName")
    section_name: str | None = Field(None, alias="SectionName")


class _StudentPhoto(_UpstreamModel):
    """The student as described by the profile response's `STUDENT_PHOTO`, a subset of `STUDENT_INFO`."""

    login_id: str | None = Field(None, alias="loginId")
    name: str | None = Field(None, alias="nameAsInSSLC")
    email: str | None = Field(None, alias="email")
    mobile: str | None = Field(None, alias="mobile")


class _ProfileResponse(_UpstreamModel):
    """The profile (dispatcher) response."""

    message: str = Field(alias="MESSAGE")
    # STUDENT_INFO has been seen on every response so far, but the examples recorded in issue #233
    # and PR #152 show only STUDENT_PHOTO. Requiring it would turn every profile request for such a
    # student into a 422, so either block will do and the profile is built from what is there.
    info: _StudentInfo | None = Field(None, alias="STUDENT_INFO")
    photo: _StudentPhoto | None = Field(None, alias="STUDENT_PHOTO")

    @model_validator(mode="after")
    def _has_student(self) -> _ProfileResponse:
        """Reject a response that describes no student at all.

        Returns:
            _ProfileResponse: The response, unchanged.

        Raises:
            ValueError: If neither STUDENT_INFO nor STUDENT_PHOTO is present.
        """
        if self.info is None and self.photo is None:
            raise ValueError("neither STUDENT_INFO nor STUDENT_PHOTO is present")
        return self

    def student(self) -> _StudentInfo:
        """Merge the two student blocks, filling STUDENT_INFO's gaps from STUDENT_PHOTO.

        Returns:
            _StudentInfo: The student details.
        """
        info = self.info or _StudentInfo()
        if self.photo is None:
            return info
        return info.model_copy(
            update={
                "login_id": info.login_id or self.photo.login_id,
                # STUDENT_PHOTO has no separate SRN; its loginId is the SRN for current students
                "srn": info.srn or self.photo.login_id,
                "name": info.name or self.photo.name,
                "email": info.email or self.photo.email,
                "mobile": info.mobile or self.photo.mobile,
            },
        )


@asynccontextmanager
async def _upstream_call(metrics: MetricsCollector, operation: str) -> AsyncIterator[list[Any]]:
    """Time one call to PESU Academy and record its outcome.

    Yields a one-element list: put the response in it and the status code is recorded too. The
    upstream is the only dependency this service has, so every call through it is timed -- when
    something is slow or broken, this is what says whether it is us or them.

    Args:
        metrics (MetricsCollector): The collector to record into.
        operation (str): The name of the upstream operation, used as a label.

    Yields:
        list[Any]: A single-element sink for the response object.

    Raises:
        BaseException: Re-raised unchanged after the failure is recorded.
    """
    sink: list[Any] = []
    started = time.perf_counter()
    # Pessimistic default, corrected once the body returns. Anything that escapes without setting
    # it -- a timeout, a connection failure -- is an error, which is the right assumption to fail to.
    outcome = "error"
    try:
        yield sink
        outcome = "success"
    except asyncio.CancelledError:
        # Kept apart from "error": a cancellation means we walked away -- a client disconnected or
        # the process is shutting down -- not that PESU Academy failed. Counting it as an error
        # would spike the upstream error rate on every deploy and every abandoned request.
        outcome = "cancelled"
        raise
    finally:
        # In a finally, so every call is counted and timed exactly once however it ended
        metrics.increment(UPSTREAM_REQUESTS, operation=operation, outcome=outcome)
        metrics.observe(UPSTREAM_LATENCY, time.perf_counter() - started, operation=operation)
        # A status exists whenever a response came back, even if something later went wrong with it
        if sink and (status := getattr(sink[0], "status_code", None)) is not None:
            metrics.increment(UPSTREAM_RESPONSES, operation=operation, status=str(status))


async def _aclose_client(client: httpx2.AsyncClient, metrics: MetricsCollector) -> None:
    """Close an HTTP client, logging rather than raising if the close itself fails.

    Cleanup failure must never replace the error that triggered the cleanup: letting `aclose()`
    propagate out of a `finally` would turn a routine 401 into a 500.

    Args:
        client (httpx2.AsyncClient): The client to close.
        metrics (MetricsCollector): The collector to record the outcome into.
    """
    try:
        await client.aclose()
    except Exception:
        # Counted, not just logged: created minus closed is how many clients are still open, and a
        # close that fails is exactly the leak this module spent a release learning to avoid.
        metrics.increment(HTTP_CLIENTS, event="close_failed")
        logging.warning("Failed to close an HTTP client cleanly.", exc_info=True)
    else:
        metrics.increment(HTTP_CLIENTS, event="closed")


async def _close_client_quietly(client: httpx2.AsyncClient, metrics: MetricsCollector) -> None:
    """Close an HTTP client, surviving both a failing close and a cancellation mid-close.

    Callers run this from a `finally`, which is exactly where a *second* cancellation can land -- a
    shutdown cancelling a task that is already unwinding from its first cancellation. A plain
    `await client.aclose()` there is abandoned part-way and the connection pool is never released,
    which is the leak this whole helper exists to prevent. Shielding the close lets it run to
    completion in its own task while the `CancelledError` still propagates to the caller, so
    cancellation semantics are unchanged.

    Args:
        client (httpx2.AsyncClient): The client to close.
        metrics (MetricsCollector): The collector to record the outcome into.
    """
    task = asyncio.ensure_future(_aclose_client(client, metrics))
    _CLOSE_TASKS.add(task)
    task.add_done_callback(_CLOSE_TASKS.discard)
    await asyncio.shield(task)


def _multipart(form: Mapping[str, str]) -> dict[str, tuple[None, str]]:
    """Encode a form as multipart/form-data fields, which is what the mobile API accepts.

    A `(None, value)` tuple is httpx's way of sending a plain multipart field rather than a file;
    passing the same form as `data=` would send it url-encoded instead.

    Args:
        form (Mapping[str, str]): The form fields.

    Returns:
        dict[str, tuple[None, str]]: The fields in the shape `files=` expects.
    """
    return {key: (None, value) for key, value in form.items()}


def _validation_failure_summary(error: ValidationError) -> list[tuple[Any, ...]]:
    """Describe a validation failure by where it failed, without the values that failed.

    A ValidationError's own message quotes the offending input, which here is a response full of
    personal data, so it is never logged or chained; this is what gets logged instead.

    Args:
        error (ValidationError): The failure to describe.

    Returns:
        list[tuple[Any, ...]]: The location and error type of each failure.
    """
    return [(*e["loc"], e["type"]) for e in error.errors()]


def _semester_from_class_name(class_name: str | None) -> str | None:
    """Get the semester from a class name such as "Sem-4, Section C".

    Args:
        class_name (str | None): The class name from upstream.

    Returns:
        str | None: The part before the comma ("Sem-4"), or None if there is none.
    """
    if class_name is None:
        return None
    return class_name.split(",", 1)[0].strip() or None


def _normalise_program(program: str) -> str:
    """Normalise a program abbreviation for lookup, so "B.Tech." and "B.TECH" are the same key.

    Args:
        program (str): The abbreviation from upstream.

    Returns:
        str: The abbreviation upper-cased, without whitespace or a trailing full stop.
    """
    return "".join(program.split()).upper().rstrip(".")


def _as_prn(login_id: str | None) -> str | None:
    """Return a login ID only if it is a PRN.

    Args:
        login_id (str | None): A login ID from upstream, which may be a PRN or an SRN.

    Returns:
        str | None: The login ID if it has the shape of a PRN, otherwise None.
    """
    if login_id is not None and PRN_PATTERN.fullmatch(login_id):
        return login_id
    return None


class PESUAcademy:
    """Class to interact with the PESU Academy server through its mobile API.

    Every login gets its own HTTP client, used for the login and the profile call and closed before
    the login returns. Nothing is cached between logins: the mobile API needs no CSRF token, so
    there is nothing worth preparing ahead of a request.

    Attributes:
        DEFAULT_FIELDS (list[str]): The profile fields returned when the caller does not choose any.

    Methods:
        authenticate: Authenticate the user with the provided username and password.
    """

    DEFAULT_FIELDS: list[str] = list(get_args(ProfileField))

    def __init__(self, metrics: MetricsCollector | None = None) -> None:
        """Initialize the PESUAcademy class.

        Args:
            metrics (MetricsCollector | None): The collector to record into. Defaults to a private
                one, so a bare PESUAcademy() still works and simply records where nobody reads.
        """
        self._metrics = metrics if metrics is not None else MetricsCollector()

    async def _login(self, client: httpx2.AsyncClient, username: str, password: str) -> _LoginResponse:
        """Log in to PESU Academy.

        Args:
            client (httpx2.AsyncClient): The HTTP client to use.
            username (str): The username of the user: their SRN, PRN, email or phone number.
            password (str): The password of the user.

        Returns:
            _LoginResponse: The parsed login response.

        Raises:
            AuthenticationError: If the credentials were rejected.
            UpstreamError: If PESU Academy could not be reached or answered unexpectedly.
        """
        form = {"userName": username, "password": password, **LOGIN_FORM}
        try:
            async with _upstream_call(self._metrics, "login") as sink:
                response = await client.post(LOGIN_URL, files=_multipart(form), headers=MOBILE_HEADERS)
                sink.append(response)
        except httpx2.HTTPError as e:
            raise UpstreamError(f"Could not reach PESU Academy to log in user={username}.") from e

        # Wrong credentials and unknown users both come back as a 401 with
        # {"statusCode": 401, "statusDescription": "Invalid Login Credentials"}
        if response.status_code == 401:
            raise AuthenticationError(f"Invalid username or password, or user does not exist for user={username}.")
        if response.status_code != 200:
            raise UpstreamError(
                f"PESU Academy answered the login for user={username} with status {response.status_code}.",
            )

        try:
            login = _LoginResponse.model_validate_json(response.content)
        except ValidationError as e:
            logging.warning(f"Unexpected login response for user={username}: {_validation_failure_summary(e)}")
            # from None: the chained error would quote the response, which is personal data
            raise UpstreamError(f"PESU Academy sent an unexpected login response for user={username}.") from None

        if login.user.login is None:
            # The marker is missing, not negative: the response has changed shape. Calling that a wrong
            # password would tell every user their credentials are bad and hide an outage as 4xx noise.
            raise UpstreamError(f"PESU Academy sent a login response without a status for user={username}.")
        if login.user.login != "SUCCESS":
            # A 200 that is not a success has not been seen, but if PESU starts reporting rejected
            # credentials this way it must not read as a successful login
            raise AuthenticationError(f"Invalid username or password, or user does not exist for user={username}.")
        return login

    async def _fetch_profile(self, client: httpx2.AsyncClient, access_token: str, username: str) -> _StudentInfo:
        """Fetch the student's profile from the dispatcher.

        Args:
            client (httpx2.AsyncClient): The HTTP client to use.
            access_token (str): The bearer token from the login response.
            username (str): The username of the user, for logging.

        Returns:
            _StudentInfo: The parsed student details.

        Raises:
            ProfileFetchError: If the profile could not be fetched.
            ProfileParseError: If the profile response did not have the expected shape.
        """
        headers = {**MOBILE_HEADERS, "Authorization": f"Bearer {access_token}"}
        try:
            async with _upstream_call(self._metrics, "profile_fetch") as sink:
                response = await client.post(DISPATCHER_URL, files=_multipart(PROFILE_FORM), headers=headers)
                sink.append(response)
        except httpx2.HTTPError as e:
            raise ProfileFetchError(f"Could not reach PESU Academy to fetch the profile of user={username}.") from e

        if response.status_code != 200:
            raise ProfileFetchError(
                f"PESU Academy answered the profile request for user={username} with status {response.status_code}.",
            )

        try:
            parsed = _ProfileResponse.model_validate_json(response.content)
        except ValidationError as e:
            self._metrics.increment(PROFILE_PARSE_ERRORS, reason="response_structure")
            logging.warning(f"Unexpected profile response for user={username}: {_validation_failure_summary(e)}")
            # from None: the chained error would quote the response, which is personal data
            raise ProfileParseError(
                f"Failed to parse the profile response from PESU Academy for user={username}.",
            ) from None

        # "SUCCESS_Record found Successfully" on success. Anything else is PESU declining to answer,
        # which is their failure to serve the profile rather than a response we cannot read.
        if not parsed.message.startswith("SUCCESS"):
            raise ProfileFetchError(f"PESU Academy did not return a profile for user={username}.")
        return parsed.student()

    def _program_name(self, program: str | None, username: str) -> str | None:
        """Expand a program abbreviation to its full name.

        Args:
            program (str | None): The abbreviation from upstream, such as "B.Tech.".
            username (str): The username of the user, for logging.

        Returns:
            str | None: The full name, or the abbreviation itself if it is not a known one.
        """
        if program is None:
            return None
        if full_name := PROGRAM_NAMES.get(_normalise_program(program)):
            return full_name
        # Not fatal: the abbreviation is still the right program, just not the form callers expect.
        # Counted so that a program missing from PROGRAM_NAMES shows up before anyone reports it.
        self._metrics.increment(PROFILE_PARSE_ERRORS, reason="unknown_program")
        logging.warning(f"Unknown program: {program} for user={username}")
        return program

    def _campus(self, identifier: str | None, username: str) -> tuple[int | None, str | None]:
        """Work out the campus from the digit after "PES" in an SRN or PRN.

        Args:
            identifier (str | None): The SRN or PRN.
            username (str): The username of the user, for logging.

        Returns:
            tuple[int | None, str | None]: The campus code and abbreviation, or (None, None).
        """
        if identifier is None or not (match := CAMPUS_CODE_PATTERN.match(identifier)):
            return None, None
        campus_code = match.group(1)
        if campus_code not in CAMPUS_NAMES:
            # Not fatal -- the profile is returned without a campus -- but it means the SRN or PRN
            # format has changed, which nothing else would surface.
            self._metrics.increment(PROFILE_PARSE_ERRORS, reason="unknown_campus_code")
            logging.warning(f"Unknown campus code: {campus_code} parsed from {identifier} for user={username}")
            return None, None
        return int(campus_code), CAMPUS_NAMES[campus_code]

    def _build_profile(self, user: _LoginUser, student: _StudentInfo, username: str) -> dict[str, Any]:
        """Merge the login and profile responses into the profile this API returns.

        The profile response is the more complete source, so most fields come from there. The login
        response fills the gaps it has been seen to leave, and is preferred for the class and section,
        which it reports as the student's current ones.

        Args:
            user (_LoginUser): The student from the login response.
            student (_StudentInfo): The student from the profile response.
            username (str): The username of the user, for logging.

        Returns:
            dict[str, Any]: The profile, with every field; None where upstream had no value.
        """
        srn = student.srn
        # Upstream uses "loginId" for the PRN and, for some students, for the SRN; only a PRN is kept
        prn = _as_prn(user.login_id) or _as_prn(student.login_id)
        # The SRN is preferred because every current student has one; older students may only have a PRN
        campus_code, campus = self._campus(srn or prn, username)
        return {
            # The name as registered, which is what the web portal showed. The login response only
            # has the first name, so it is the fallback.
            "name": student.name or user.name,
            "prn": prn,
            "srn": srn,
            "program": self._program_name(user.program or student.program, username),
            "branch": student.branch,
            "semester": _semester_from_class_name(user.class_name or student.class_name),
            "section": user.section_name or student.section_name,
            "email": user.email or student.email,
            "phone": user.phone or student.mobile,
            "campusCode": campus_code,
            "campus": campus,
        }

    async def authenticate(
        self,
        username: str,
        password: str,
        profile: bool = False,
        fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """Authenticate the user with the provided username and password.

        Args:
            username (str): The username of the user: their SRN, PRN, email or phone number.
            password (str): The password of the user.
            profile (bool, optional): Whether to fetch the profile information or not. Defaults to False.
            fields (Optional[list[str]], optional): The fields to fetch from the profile.
            Defaults to None, which means all default fields will be fetched.

        Returns:
            dict[str, Any]: A dictionary containing the authentication status, message,
            and optionally the profile information.

        Raises:
            UpstreamError: If the login response had no token to fetch the profile with.
        """
        # Default fields to fetch if fields is not provided
        fields = self.DEFAULT_FIELDS if fields is None else fields
        # Check if fields is not the default fields and enable field filtering
        field_filtering = fields != self.DEFAULT_FIELDS

        logging.info(
            f"Connecting to PESU Academy with user={username}, profile={profile}, fields={fields} ...",
        )

        # One client per login, shared by its two calls and by nobody else, so no session state can
        # leak from one user's login into another's. Redirects are not followed: these endpoints answer
        # directly, so a redirect means something in front of them changed, and is reported as a 502.
        client = httpx2.AsyncClient(timeout=UPSTREAM_TIMEOUT_SECONDS)
        self._metrics.increment(HTTP_CLIENTS, event="created")
        # This client belongs to this request, so close it on every exit path, not just success
        try:
            login = await self._login(client, username, password)
            logging.info(f"Login successful for user={username}.")
            result: dict[str, Any] = {"status": True, "message": "Login successful."}

            if profile:
                logging.info(f"Profile data requested for user={username}. Fetching profile data...")
                if login.access_token is None:
                    raise UpstreamError(f"PESU Academy sent no access token for user={username}.")
                student = await self._fetch_profile(client, login.access_token, username)
                result["profile"] = self._build_profile(login.user, student, username)
                logging.info(f"Complete profile information retrieved for user={username}: {result['profile']}.")
                # Recorded at the branch itself rather than from the request body, so it reflects
                # what actually happened: a caller who passes exactly the default field list has
                # specified fields but triggers no filtering.
                self._metrics.increment(PROFILE_FIELD_FILTERING, enabled=str(field_filtering).lower())
                # Filter the fields if field filtering is enabled
                if field_filtering:
                    result["profile"] = {key: value for key, value in result["profile"].items() if key in fields}
                    logging.info(
                        f"Field filtering enabled. Filtered profile data for user={username}: {result['profile']}",
                    )

            logging.info(f"Authentication process for user={username} completed successfully.")
            return result
        finally:
            await _close_client_quietly(client, self._metrics)
