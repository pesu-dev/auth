"""PESUAcademy class that serves as an interface to the PESU Academy mobile API."""

from __future__ import annotations

import asyncio
import logging
import re
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
    from collections.abc import AsyncIterator, Callable, Mapping

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
    "firstName",
    "middleName",
    "lastName",
    "branchShortCode",
    "institute",
    "rollNumber",
    "gender",
    "dateOfBirth",
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
# PESU stores a date of birth as the epoch milliseconds of midnight IST on that day. Read in UTC, the
# same instant is 18:30 on the day before, so the timezone is what makes the date right.
IST = timezone(timedelta(hours=5, minutes=30))
ISO_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")
# What upstream sends for a value it does not have. "NA" is what the web portal showed for a student
# with no current class; it is a placeholder, not a value, so it is treated like a missing one.
MISSING_VALUES = frozenset({"", "NA"})
# A PRN is "PES", the campus digit, the year of joining and a 5-digit number: PES1201800001.
# An SRN is "PES", the campus digit, the program (UG, PG, ...), the last two digits of the year of
# joining, the branch and a 3-digit number: PES2UG25CS001. Students who joined before SRNs were
# introduced have an SRN that is their PRN. So the shapes never collide: an all-digit ID is always
# the student's PRN, and one with letters is always their SRN.
PRN_PATTERN = re.compile(r"PES\d{10}")
SRN_PATTERN = re.compile(r"PES\d[A-Z]{2}\d{2}[A-Z]{2}\d{3}")
# The campus digit is in the same place in both
CAMPUS_CODE_PATTERN = re.compile(r"PES(\d)")


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
# program, branch, class, contact details) stay strict, so a change to them is still a 422.
Secondary = WrapValidator(_none_if_invalid)


class _LoginUser(_UpstreamModel):
    """The student as described by the login response's `mobileJsonObject`."""

    login: str | None = None
    # The first name only, despite the key
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    program: str | None = None
    class_name: str | None = Field(None, alias="className")
    section_name: str | None = Field(None, alias="sectionName")
    login_id: str | None = Field(None, alias="loginId")
    # Already a YYYY-MM-DD string here, unlike the profile response's timestamp
    date_of_birth: Annotated[str | None, Secondary] = Field(None, alias="dateofBirth")


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
    """The student as described by the profile response's `STUDENT_PHOTO`, a subset of `STUDENT_INFO`."""

    login_id: str | None = Field(None, alias="loginId")
    name: str | None = Field(None, alias="nameAsInSSLC")
    first_name: Annotated[str | None, Secondary] = Field(None, alias="firstName")
    email: str | None = Field(None, alias="email")
    mobile: str | None = Field(None, alias="mobile")
    institute: Annotated[str | None, Secondary] = Field(None, alias="instituteName")
    gender: Annotated[str | None, Secondary] = None
    date_of_birth: Annotated[int | None, Secondary] = Field(None, alias="dateOfBirth")


class _UserRole(_UpstreamModel):
    """The profile response's `USER_ROLE` block, read only for the PRN it carries."""

    login_id: Annotated[str | None, Secondary] = Field(None, alias="LoginId")


class _Semester(_UpstreamModel):
    """One of the student's semesters, from the profile response's `STUDENT_SEMESTERS`."""

    roll_number: Annotated[int | None, Secondary] = Field(None, alias="studentRollNo")
    # Orders the semesters chronologically; the list itself is not guaranteed to be in order
    order: Annotated[int | None, Secondary] = Field(None, alias="batchClassOrder")


class _Student(_UpstreamModel):
    """The student, merged from the blocks of the profile response."""

    # Kept apart rather than merged, and told apart by shape when the profile is built (see
    # PRN_PATTERN). For students whose PRN and SRN differ, PESU has been seen to send the PRN as
    # STUDENT_INFO's LoginId and USER_ROLE's LoginId, and the SRN as STUDENT_INFO's SRN and
    # STUDENT_PHOTO's loginId. For older students all of them are the same ID.
    login_id: str | None = None
    role_login_id: str | None = None
    photo_login_id: str | None = None
    srn: str | None = None
    name: str | None = None
    first_name: str | None = None
    middle_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    mobile: str | None = None
    program: str | None = None
    branch: str | None = None
    branch_short_code: str | None = None
    class_name: str | None = None
    section_name: str | None = None
    institute: str | None = None
    roll_number: int | None = None
    gender: str | None = None
    date_of_birth: int | None = None


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
    # STUDENT_INFO has been seen on every response so far, but the examples recorded in issue #233
    # and PR #152 show only STUDENT_PHOTO. Requiring it would turn every profile request for such a
    # student into a 422, so either block will do and the profile is built from what is there.
    info: _StudentInfo | None = Field(None, alias="STUDENT_INFO")
    photo: _StudentPhoto | None = Field(None, alias="STUDENT_PHOTO")
    # Secondary, like the semesters: a USER_ROLE or STUDENT_SEMESTERS of an unexpected shape -- PESU
    # sends {} for an empty block, for one -- is dropped rather than failing the profile. Each semester
    # is too, so one malformed entry does not cost the others.
    role: Annotated[_UserRole | None, Secondary] = Field(None, alias="USER_ROLE")
    semesters: Annotated[list[Annotated[_Semester | None, Secondary]] | None, Secondary] = Field(
        None,
        alias="STUDENT_SEMESTERS",
    )

    @model_validator(mode="after")
    def _has_student(self) -> _ProfileResponse:
        """Reject a response that describes no student at all.

        A block counts only if it holds a value. PESU sends `{}` for an empty block (PLACEMENT_DETAILS
        is one), and since every field is optional, `{}` -- or a block of only unknown or null keys --
        would otherwise parse into an all-empty block and pass as a profile.

        Returns:
            _ProfileResponse: The response, unchanged.

        Raises:
            ValueError: If neither STUDENT_INFO nor STUDENT_PHOTO holds any student data.
        """
        if not _has_values(self.info) and not _has_values(self.photo):
            raise ValueError("neither STUDENT_INFO nor STUDENT_PHOTO holds any student data")
        return self

    def student(self) -> _Student:
        """Merge the student blocks, filling STUDENT_INFO's gaps from STUDENT_PHOTO.

        Returns:
            _Student: The student details.
        """
        info = self.info or _StudentInfo()
        photo = self.photo or _StudentPhoto()
        return _Student(
            login_id=info.login_id,
            role_login_id=(self.role or _UserRole()).login_id,
            photo_login_id=photo.login_id,
            srn=info.srn,
            name=info.name or photo.name,
            first_name=info.first_name or photo.first_name,
            middle_name=info.middle_name,
            last_name=info.last_name,
            email=info.email or photo.email,
            mobile=info.mobile or photo.mobile,
            program=info.program,
            branch=info.branch,
            branch_short_code=info.branch_short_code,
            class_name=info.class_name,
            section_name=info.section_name,
            institute=photo.institute,
            roll_number=self._current_roll_number(),
            gender=photo.gender,
            date_of_birth=info.date_of_birth or photo.date_of_birth,
        )

    def _current_roll_number(self) -> int | None:
        """Get the roll number from the student's latest semester.

        Roll numbers change from one semester to the next, so only the most recent one is current. If the
        latest semester has no usable roll number, there is no current one: an earlier semester's would
        be wrong rather than missing.

        Returns:
            int | None: The latest semester's roll number, or None if it has none or there are no semesters.
        """
        semesters = [s for s in self.semesters or () if s is not None and s.order is not None]
        if not semesters:
            return None
        return max(semesters, key=lambda semester: semester.order).roll_number


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


def _as_srn(login_id: str | None) -> str | None:
    """Return a login ID only if it is a new-style SRN, the kind with letters.

    Args:
        login_id (str | None): A login ID from upstream, which may be a PRN or an SRN.

    Returns:
        str | None: The login ID if it has the shape of a new-style SRN, otherwise None.
    """
    if login_id is not None and SRN_PATTERN.fullmatch(login_id):
        return login_id
    return None


def _first(convert: Callable[[str | None], str | None], *values: str | None) -> str | None:
    """Return the first value that a converter accepts.

    Args:
        convert (Callable[[str | None], str | None]): Returns the value if it is acceptable, else None.
        *values (str | None): The candidates, in order of preference.

    Returns:
        str | None: The first accepted value, or None if there is none.
    """
    return next((accepted for value in values if (accepted := convert(value)) is not None), None)


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


def _iso_date(value: str | None) -> str | None:
    """Return a date string only if it is already YYYY-MM-DD.

    Args:
        value (str | None): A date string from upstream.

    Returns:
        str | None: The value, or None if it is missing or in another format.
    """
    if value is not None and ISO_DATE_PATTERN.fullmatch(value):
        return value
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

    def _build_profile(self, user: _LoginUser, student: _Student, username: str) -> dict[str, Any]:
        """Merge the login and profile responses into the profile this API returns.

        The profile response is the more complete source, so most fields come from there. The login
        response fills the gaps it has been seen to leave, and is preferred for the class and section,
        which it reports as the student's current ones.

        Args:
            user (_LoginUser): The student from the login response.
            student (_Student): The student from the profile response.
            username (str): The username of the user, for logging.

        Returns:
            dict[str, Any]: The profile, with every field; None where upstream had no value.
        """
        # PESU puts the PRN or the SRN under "loginId" in each block, so they are told apart by shape.
        # The one field labelled as the SRN comes first, as sent. Then any new-style SRN, which cannot
        # be anything else. Last, STUDENT_PHOTO's loginId if it is a PRN: that block's loginId has been
        # seen to hold the SRN, and an older student's SRN is their PRN.
        srn = (
            student.srn
            or _first(_as_srn, student.photo_login_id, user.login_id, student.login_id)
            or _first(_as_prn, student.photo_login_id)
        )
        # Any PRN-shaped ID is the PRN, wherever it is: a new-style SRN always has letters, and an older
        # student's SRN is their PRN anyway. The login's loginId, STUDENT_INFO's LoginId and
        # USER_ROLE's LoginId have each been seen to hold it.
        prn = _first(
            _as_prn,
            user.login_id,
            student.login_id,
            student.role_login_id,
            student.photo_login_id,
            student.srn,
        )
        # The SRN's campus digit is the same as the PRN's; the SRN comes first as the ID PESU labels
        campus_code, campus = self._campus(srn or prn, username)
        # Every field is a value PESU sent, or null; nothing is guessed. The name, program and branch code
        # in particular are returned as PESU wrote them, with no fallback that could stand in for them
        # wrongly (the login's "name" is only the first name, for one).
        return {
            # The name as registered, which is what the web portal showed
            "name": student.name,
            "prn": prn,
            "srn": srn,
            # The abbreviation PESU sends, such as "B.Tech.": it sends no full name, and a table of them
            # here would be a guess that clients can make better themselves
            "program": user.program or student.program,
            "branch": student.branch,
            "semester": _semester_from_class_name(user.class_name or student.class_name),
            "section": user.section_name or student.section_name,
            "email": user.email or student.email,
            "phone": user.phone or student.mobile,
            "campusCode": campus_code,
            "campus": campus,
            # The login's "name" is the first name too
            "firstName": student.first_name or user.name,
            "middleName": student.middle_name,
            "lastName": student.last_name,
            "branchShortCode": student.branch_short_code,
            "institute": student.institute,
            "rollNumber": student.roll_number,
            "gender": student.gender,
            "dateOfBirth": _date_from_epoch_ms(student.date_of_birth) or _iso_date(user.date_of_birth),
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
