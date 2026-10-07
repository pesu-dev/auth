"""PESUAcademy class that serves as an interface to the PESU Academy mobile API."""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, get_args

import httpx2
from pydantic import ValidationError

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
from app.models.profile import ProfileField
from app.models.upstream import UNEXPECTED_FIELDS, ErrorEnvelope, LoginResponse, ProfileResponse, Student

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Mapping

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


# Strong references to in-flight client closes. A close that outlives the coroutine which asked
# for it (see _close_client_quietly) would otherwise be a bare task, free to be garbage collected
# mid-flight. See https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task
_CLOSE_TASKS: set[asyncio.Task[None]] = set()


@asynccontextmanager
async def _upstream_call(metrics: MetricsCollector, operation: str) -> AsyncGenerator[list[Any]]:
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
    """Describe a validation failure by where and why it failed, without the values that failed.

    A ValidationError's own message quotes the offending input, which here is a response full of
    personal data, so it is never logged or chained; this is what gets logged instead. Each error's
    `msg` is safe to include: pydantic keeps the input apart from it, in `input`, which is left out,
    and the msg is what says why a failure with no location (a whole-response check) failed.

    Args:
        error (ValidationError): The failure to describe.

    Returns:
        list[tuple[Any, ...]]: The location, error type and message of each failure.
    """
    return [(*e["loc"], e["type"], e["msg"]) for e in error.errors()]


def _error_envelope_status(content: bytes) -> int | None:
    """Get the error status from a response that is PESU's error envelope.

    Args:
        content (bytes): The response body.

    Returns:
        int | None: The envelope's status if the body is one that reports an error, otherwise None.
    """
    try:
        envelope = ErrorEnvelope.model_validate_json(content)
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

    async def _login(self, client: httpx2.AsyncClient, username: str, password: str) -> LoginResponse:
        """Log in to PESU Academy.

        Args:
            client (httpx2.AsyncClient): The HTTP client to use.
            username (str): The username of the user: their SRN, PRN, email or phone number.
            password (str): The password of the user.

        Returns:
            LoginResponse: The parsed login response.

        Raises:
            AuthenticationError: If the credentials were rejected.
            UpstreamError: If PESU Academy could not be reached or returned an unexpected response.
        """
        form = {"userName": username, "password": password, **LOGIN_FORM}
        try:
            async with _upstream_call(self._metrics, "login") as sink:
                response = await client.post(LOGIN_URL, files=_multipart(form), headers=MOBILE_HEADERS)
                sink.append(response)
        except httpx2.HTTPError as e:
            raise UpstreamError(detail=f"Could not reach PESU Academy to log in user={username}.") from e

        # Wrong credentials and unknown users both come back as a 401 with
        # {"statusCode": 401, "statusDescription": "Invalid Login Credentials"}
        if response.status_code == 401:
            raise AuthenticationError(
                detail=f"Invalid username or password, or user does not exist for user={username}."
            )
        if response.status_code != 200:
            raise UpstreamError(
                detail=f"PESU Academy answered the login for user={username} with status {response.status_code}.",
            )

        unexpected: list[str] = []
        try:
            login = LoginResponse.model_validate_json(response.content, context={UNEXPECTED_FIELDS: unexpected})
        except ValidationError as e:
            logging.warning(f"Unexpected login response for user={username}: {_validation_failure_summary(e)}")
            # from None: the chained error would quote the response, which is personal data
            raise UpstreamError(detail=f"PESU Academy sent an unexpected login response for user={username}.") from None

        if unexpected:
            logging.warning(
                f"Ignored values of an unexpected shape in the login response for user={username}: {unexpected}"
            )
        # Rejected credentials have only ever been seen as an HTTP 401, handled above. A 200 that does not
        # say SUCCESS -- whether the marker is missing or holds anything else -- is a response nobody has
        # seen, so it is reported as PESU's failure. Calling it a wrong password would tell every user
        # their credentials are bad, and hide an upstream change as 4xx noise.
        if login.user.login != "SUCCESS":
            raise UpstreamError(detail=f"PESU Academy did not report a successful login for user={username}.")
        return login

    async def _fetch_profile(self, client: httpx2.AsyncClient, access_token: str, username: str) -> Student:
        """Fetch the student's profile from the dispatcher.

        Args:
            client (httpx2.AsyncClient): The HTTP client to use.
            access_token (str): The bearer token from the login response.
            username (str): The username of the user, for logging.

        Returns:
            Student: The parsed student details.

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
            raise ProfileFetchError(
                detail=f"Could not reach PESU Academy to fetch the profile of user={username}."
            ) from e

        if response.status_code != 200:
            raise ProfileFetchError(
                detail=(
                    f"PESU Academy answered the profile request for user={username} with status {response.status_code}."
                ),
            )

        unexpected: list[str] = []
        try:
            parsed = ProfileResponse.model_validate_json(response.content, context={UNEXPECTED_FIELDS: unexpected})
        except ValidationError as e:
            # PESU reporting an error is PESU failing to serve the profile, not a response we cannot
            # read: a 502 like the login's, rather than the 422 that means their API has changed
            if (status := _error_envelope_status(response.content)) is not None:
                raise ProfileFetchError(
                    detail=f"PESU Academy answered the profile request for user={username} with error status {status}.",
                ) from None
            self._metrics.increment(PROFILE_PARSE_ERRORS, reason="response_structure")
            logging.warning(f"Unexpected profile response for user={username}: {_validation_failure_summary(e)}")
            # from None: the chained error would quote the response, which is personal data
            raise ProfileParseError(
                detail=f"Failed to parse the profile response from PESU Academy for user={username}.",
            ) from None

        # Anything but success is PESU declining to answer, which is their failure to serve the profile
        # rather than a response we cannot read, whether or not it describes a student.
        if not parsed.succeeded:
            raise ProfileFetchError(detail=f"PESU Academy did not return a profile for user={username}.")
        self._report_unread_fields("missing_field", parsed.missing_fields(), username)
        self._report_unread_fields("unexpected_value", unexpected, username)
        return parsed.student()

    def _report_unread_fields(self, reason: str, fields: list[str], username: str) -> None:
        """Count and log the profile fields that are null because PESU did not send them as expected.

        The caller only ever sees null, as for a student with no value. These are different: PESU did not
        send the field at all, or sent it in a shape nobody has seen, which means its API changed. Counted
        once per field, so a change shows up on the dashboard rather than as quietly missing data.

        Args:
            reason (str): "missing_field" for a field PESU did not send, "unexpected_value" for one it
                sent in an unexpected shape.
            fields (list[str]): The fields, named as PESU names them. Never their values.
            username (str): The username of the user, for logging.
        """
        if not fields:
            return
        self._metrics.increment(PROFILE_PARSE_ERRORS, float(len(fields)), reason=reason)
        logging.warning(f"Profile fields left null ({reason}) for user={username}: {fields}")

    def _campus_code(self, campus: str | None, username: str) -> int | None:
        """Get the campus code for a campus, named as PESU names it.

        Args:
            campus (str | None): The campus's institute name from upstream, such as "PES University (Ring Road)".
            username (str): The username of the user, for logging.

        Returns:
            int | None: The campus code, or None if there is no campus name or it is not a known one.
        """
        if campus is None:
            return None
        if (campus_code := CAMPUS_CODES.get(campus)) is None:
            # Not fatal -- the campus is still returned as PESU named it -- but it means a campus, or the
            # way PESU writes its name, is new, which nothing else would surface.
            self._metrics.increment(PROFILE_PARSE_ERRORS, reason="unknown_campus_code")
            logging.warning(f"Unknown campus name: {campus} for user={username}")
        return campus_code

    def _build_profile(self, student: Student, username: str) -> dict[str, Any]:
        """Build the profile this API returns from the profile response.

        Every field STUDENT_INFO has is taken from STUDENT_INFO alone, as PESU wrote it, or is null: no
        other block, and not the login response, stands in for a value it lacks. Only what STUDENT_INFO
        does not have comes from elsewhere: the campus and gender, from STUDENT_PHOTO.

        Args:
            student (Student): The student from the profile response.
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
            "campusCode": self._campus_code(student.campus, username),
            "campus": student.campus,
            "firstName": info.first_name,
            "middleName": info.middle_name,
            "lastName": info.last_name,
            "branchShortCode": info.branch_short_code,
            "gender": student.gender,
            "dateOfBirth": _date_from_epoch_ms(info.date_of_birth),
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
            AuthenticationError: If PESU Academy rejected the credentials.
            UpstreamError: If PESU Academy could not be reached to log in or returned an unexpected response to
                the login, or the login gave no token to fetch the profile with.
            ProfileFetchError: If the profile could not be fetched, or PESU Academy declined to serve it.
            ProfileParseError: If the profile response did not have the expected shape.
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
                    raise UpstreamError(detail=f"PESU Academy sent no access token for user={username}.")
                student = await self._fetch_profile(client, login.access_token, username)
                result["profile"] = self._build_profile(student, username)
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
