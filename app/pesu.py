"""PESUAcademy class that serves as an interface to the PESU Academy mobile API."""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Annotated, Any, Literal, get_args

import httpx2
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    ValidationInfo,
    ValidatorFunctionWrapHandler,
    WrapValidator,
    field_validator,
    model_validator,
)

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
    "mobile",
    "campusCode",
    "campus",
    "firstName",
    "middleName",
    "lastName",
    "branchShortCode",
    "gender",
    "dateOfBirth",
    "isParent",
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

# The campus code for each campus's institute name, as PESU writes it. The codes are the campus digit
# in the student's PRN and SRN, which is what this API has always returned. Checked against students
# of both campuses.
CAMPUS_CODES = {"PES University (Ring Road)": 1, "PES University (Electronic City)": 2}
# PESU stores a date of birth as the epoch milliseconds of midnight IST on that day. Read in UTC, the
# same instant is 18:30 on the day before, so the timezone is what makes the date right.
IST = timezone(timedelta(hours=5, minutes=30))
# What upstream sends for a value it does not have. "NA" is what the web portal showed for a student
# with no current class; it is a placeholder, not a value, so it is treated like a missing one.
MISSING_VALUES = frozenset({"", "NA"})


# Strong references to in-flight client closes. A close that outlives the coroutine which asked
# for it (see _close_client_quietly) would otherwise be a bare task, free to be garbage collected
# mid-flight. See https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task
_CLOSE_TASKS: set[asyncio.Task[None]] = set()


class _UpstreamModel(BaseModel):
    """Base for the response shapes read from PESU Academy.

    Only the fields this service returns are declared; everything else is dropped as the response is
    parsed. Those responses also carry the student's photo, blood group, addresses, marks and their
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


def _none_if_invalid(value: Any, handler: ValidatorFunctionWrapHandler, info: ValidationInfo) -> Any:  # noqa: ANN401
    """Validate a secondary field, turning a value of an unexpected shape into None.

    Args:
        value (Any): The raw value from the response.
        handler (ValidatorFunctionWrapHandler): The field's own validation.
        info (ValidationInfo): Which field is being validated.

    Returns:
        Any: The validated value, or None if it did not validate.
    """
    try:
        return handler(value)
    except ValidationError:
        # The field's name only: the value is from a response full of personal data
        logging.warning(f"Ignored an unexpected value for {info.field_name} in a PESU Academy response.")
        return None


# For the fields that add to a profile rather than make one. If PESU changes the shape of one of
# these, that field is null and the rest of the profile still comes back; the core fields (name, IDs,
# program, branch, class, contact details, campus) stay strict, so a change to them is still a 422.
Secondary = WrapValidator(_none_if_invalid)


class _LoginUser(_UpstreamModel):
    """The user as described by the login response's `mobileJsonObject`.

    Read for the success marker and for isParent, which only the login response has. The rest of the
    profile comes from the profile response, so the login response's copies of the same details (some
    of them partial: its "name" is the first name only) are never mixed into it.
    """

    login: str | None = None
    # 0 for a student's own account; PESU Academy also has parent accounts
    is_parent: Annotated[bool | None, Secondary] = Field(None, alias="isParent")


class _LoginResponse(_UpstreamModel):
    """The login response: the student, and the token the profile call needs."""

    user: _LoginUser = Field(alias="mobileJsonObject")
    # repr=False so the bearer token cannot reach a log through the model's repr
    access_token: str | None = Field(None, alias="accessToken", repr=False)


class _StudentInfo(_UpstreamModel):
    """The student as described by the profile response's `STUDENT_INFO`, the source of every field it has.

    For students whose PRN and SRN differ, PESU sends the PRN as LoginId and the SRN as SRN; for students
    who joined before SRNs existed, both hold the same ID.
    """

    prn: str | None = Field(None, alias="LoginId")
    srn: str | None = Field(None, alias="SRN")
    name: str | None = Field(None, alias="NameAsInSSLC")
    first_name: Annotated[str | None, Secondary] = Field(None, alias="FirstName")
    middle_name: Annotated[str | None, Secondary] = Field(None, alias="MiddleName")
    last_name: Annotated[str | None, Secondary] = Field(None, alias="LastName")
    email: str | None = Field(None, alias="Email")
    mobile: str | None = Field(None, alias="Mobile")
    program: str | None = Field(None, alias="ProgramAbbreviation")
    branch: str | None = Field(None, alias="Branch")
    branch_short_code: Annotated[str | None, Secondary] = Field(None, alias="BranchAbbreviation")
    class_name: str | None = Field(None, alias="ClassName")
    section_name: str | None = Field(None, alias="SectionName")
    date_of_birth: Annotated[int | None, Secondary] = Field(None, alias="DateOfBirth")


class _StudentPhoto(_UpstreamModel):
    """The profile response's `STUDENT_PHOTO`, read only for what STUDENT_INFO does not have."""

    # The campus, such as "PES University (Ring Road)"
    institute: str | None = Field(None, alias="instituteName")
    gender: Annotated[str | None, Secondary] = None


class _Student(_UpstreamModel):
    """The student, from the blocks of the profile response."""

    info: _StudentInfo
    institute: str | None = None
    gender: str | None = None


class _ErrorEnvelope(_UpstreamModel):
    """PESU's error body, which it can send with an HTTP 200, as in {"status": 400, "message": "..."}."""

    status: int
    message: str | None = None


def _has_values(block: BaseModel | None) -> bool:
    """Tell whether a parsed block holds any value at all.

    Args:
        block (BaseModel | None): The block, or None if it was absent.

    Returns:
        bool: True if the block is present and at least one of its fields is not None.
    """
    return block is not None and any(value is not None for value in block.model_dump().values())


class _ProfileResponse(_UpstreamModel):
    """The profile (dispatcher) response."""

    message: str = Field(alias="MESSAGE")
    info: _StudentInfo | None = Field(None, alias="STUDENT_INFO")
    photo: _StudentPhoto | None = Field(None, alias="STUDENT_PHOTO")

    @model_validator(mode="after")
    def _has_student(self) -> _ProfileResponse:
        """Reject a response whose STUDENT_INFO describes no student.

        STUDENT_INFO is where every core field comes from, and nothing stands in for it. A block counts
        only if it holds a value: PESU sends `{}` for an empty block (PLACEMENT_DETAILS is one), and
        since every field is optional, `{}` -- or a block of only unknown or null keys -- would otherwise
        parse into an all-empty block and pass as a profile.

        Returns:
            _ProfileResponse: The response, unchanged.

        Raises:
            ValueError: If STUDENT_INFO is missing or holds no student data.
        """
        if not _has_values(self.info):
            raise ValueError("STUDENT_INFO holds no student data")
        return self

    def student(self) -> _Student:
        """Gather the student from the blocks of the response.

        Returns:
            _Student: The student details.
        """
        photo = self.photo or _StudentPhoto()
        return _Student(info=self.info, institute=photo.institute, gender=photo.gender)


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


def _error_envelope_status(content: bytes) -> int | None:
    """Get the error status from a response that is PESU's error envelope.

    Args:
        content (bytes): The response body.

    Returns:
        int | None: The envelope's status if the body is one that reports an error, otherwise None.
    """
    try:
        envelope = _ErrorEnvelope.model_validate_json(content)
    except ValidationError:
        return None
    return envelope.status if envelope.status != 200 else None


def _date_from_epoch_ms(milliseconds: int | None) -> str | None:
    """Turn PESU's date-of-birth timestamp into an ISO date.

    Args:
        milliseconds (int | None): Epoch milliseconds of midnight IST on the date.

    Returns:
        str | None: The date as YYYY-MM-DD, or None if there is none or it is out of range.
    """
    if milliseconds is None:
        return None
    try:
        return datetime.fromtimestamp(milliseconds / 1000, tz=IST).date().isoformat()
    except OverflowError, OSError, ValueError:
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

        # Rejected credentials have only ever been seen as an HTTP 401, handled above. A 200 that does not
        # say SUCCESS -- whether the marker is missing or holds anything else -- is a response nobody has
        # seen, so it is reported as PESU's failure. Calling it a wrong password would tell every user
        # their credentials are bad, and hide an upstream change as 4xx noise.
        if login.user.login != "SUCCESS":
            raise UpstreamError(f"PESU Academy did not report a successful login for user={username}.")
        return login

    async def _fetch_profile(self, client: httpx2.AsyncClient, access_token: str, username: str) -> _Student:
        """Fetch the student's profile from the dispatcher.

        Args:
            client (httpx2.AsyncClient): The HTTP client to use.
            access_token (str): The bearer token from the login response.
            username (str): The username of the user, for logging.

        Returns:
            _Student: The parsed student details.

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
            # PESU reporting an error is PESU failing to serve the profile, not a response we cannot
            # read: a 502 like the login's, rather than the 422 that means their API has changed
            if (status := _error_envelope_status(response.content)) is not None:
                raise ProfileFetchError(
                    f"PESU Academy answered the profile request for user={username} with error status {status}.",
                ) from None
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

    def _campus_code(self, institute: str | None, username: str) -> int | None:
        """Get the campus code for a campus's institute name.

        Args:
            institute (str | None): The institute name from upstream, such as "PES University (Ring Road)".
            username (str): The username of the user, for logging.

        Returns:
            int | None: The campus code, or None if there is no institute name or it is not a known one.
        """
        if institute is None:
            return None
        if (campus_code := CAMPUS_CODES.get(institute)) is None:
            # Not fatal -- the campus is still returned as PESU named it -- but it means a campus, or the
            # way PESU writes its name, is new, which nothing else would surface.
            self._metrics.increment(PROFILE_PARSE_ERRORS, reason="unknown_campus_code")
            logging.warning(f"Unknown institute name: {institute} for user={username}")
        return campus_code

    def _build_profile(self, user: _LoginUser, student: _Student, username: str) -> dict[str, Any]:
        """Build the profile this API returns from the profile and login responses.

        Every field STUDENT_INFO has is taken from STUDENT_INFO alone, as PESU wrote it, or is null: no
        other block, and not the login response, stands in for a value it lacks. Only what STUDENT_INFO
        does not have comes from elsewhere: the campus and gender from STUDENT_PHOTO, and isParent from
        the login response.

        Args:
            user (_LoginUser): The user from the login response.
            student (_Student): The student from the profile response.
            username (str): The username of the user, for logging.

        Returns:
            dict[str, Any]: The profile, with every field; None where upstream had no value.
        """
        info = student.info
        # Worked out rather than copied: the campus code, a fixed mapping of the campus's name, and the
        # date of birth, converted from a timestamp
        return {
            # The name as registered, which is what the web portal showed
            "name": info.name,
            "prn": info.prn,
            "srn": info.srn,
            # The abbreviation PESU sends, such as "B.Tech.": it sends no full name, and a table of them
            # here would be a guess that clients can make better themselves
            "program": info.program,
            "branch": info.branch,
            # Such as "Sem-4". The login response's className adds the section ("Sem-4, Section C"),
            # but STUDENT_INFO's is the semester alone.
            "semester": info.class_name,
            "section": info.section_name,
            "email": info.email,
            "mobile": info.mobile,
            "campusCode": self._campus_code(student.institute, username),
            "campus": student.institute,
            "firstName": info.first_name,
            "middleName": info.middle_name,
            "lastName": info.last_name,
            "branchShortCode": info.branch_short_code,
            "gender": student.gender,
            "dateOfBirth": _date_from_epoch_ms(info.date_of_birth),
            "isParent": user.is_parent,
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
