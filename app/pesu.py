"""PESUAcademy class that serves as an interface to the PESU Academy website."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal, get_args

import httpx2
from selectolax.parser import HTMLParser, Node

from app.exceptions.authentication import (
    AuthenticationError,
    CSRFTokenError,
    ProfileFetchError,
    ProfileParseError,
)
from app.metrics.collector import (
    CSRF_CACHE,
    HTTP_CLIENTS,
    PREFETCH_TASKS,
    PROFILE_FIELD_FILTERING,
    PROFILE_PARSE_ERRORS,
    UPSTREAM_LATENCY,
    UPSTREAM_REQUESTS,
    UPSTREAM_RESPONSES,
    MetricsCollector,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

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


# Strong references to in-flight client closes. A close that outlives the coroutine which asked
# for it (see _close_client_quietly) would otherwise be a bare task, free to be garbage collected
# mid-flight. See https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task
_CLOSE_TASKS: set[asyncio.Task[None]] = set()


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

    Most callers run this from an `except BaseException` handler or a `finally`, which is exactly
    where a *second* cancellation can land -- a shutdown cancelling a task that is already
    unwinding from its first cancellation. A plain `await client.aclose()` there is abandoned
    part-way and the connection pool is never released, which is the leak this whole helper
    exists to prevent. Shielding the close lets it run to completion in its own task while the
    `CancelledError` still propagates to the caller, so cancellation semantics are unchanged.

    Args:
        client (httpx2.AsyncClient): The client to close.
        metrics (MetricsCollector): The collector to record the outcome into.
    """
    task = asyncio.ensure_future(_aclose_client(client, metrics))
    _CLOSE_TASKS.add(task)
    task.add_done_callback(_CLOSE_TASKS.discard)
    await asyncio.shield(task)


class PESUAcademy:
    """Class to interact with the PESU Academy server.

    This class provides methods to authenticate users, fetch profile information, and handle CSRF token management.

    Attributes:
        DEFAULT_FIELDS (list[str]): The default fields to fetch from the profile page.
        PROFILE_PAGE_HEADER_TO_KEY_MAP (dict[str, str]): A mapping of profile page headers to the corresponding keys
        in the profile dictionary.

    Methods:
        prefetch_client_with_csrf_token: Prefetch a new client with an unauthenticated CSRF token.
        close_client: Close the cached client and stop any prefetch still in flight.
        get_profile_information: Get the profile information of the user.
        authenticate: Authenticate the user with the provided username and password.
    """

    DEFAULT_FIELDS: list[str] = list(get_args(ProfileField))

    PROFILE_PAGE_HEADER_TO_KEY_MAP = {
        "Name": "name",
        "PESU Id": "prn",
        "SRN": "srn",
        "Program": "program",
        "Branch": "branch",
        "Semester": "semester",
        "Section": "section",
    }

    def __init__(self, metrics: MetricsCollector | None = None) -> None:
        """Initialize the PESUAcademy class.

        Args:
            metrics (MetricsCollector | None): The collector to record into. Defaults to a private
                one, so a bare PESUAcademy() still works and simply records where nobody reads.
        """
        self._metrics = metrics if metrics is not None else MetricsCollector()
        self._csrf_token: str | None = None
        self._client: httpx2.AsyncClient | None = None
        self._csrf_lock = asyncio.Lock()
        # Strong references to in-flight prefetch tasks, so they cannot be garbage collected
        # mid-flight. See https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task
        self._prefetch_tasks: set[asyncio.Task[None]] = set()

    async def _fetch_new_client_with_csrf_token(self) -> tuple[httpx2.AsyncClient, str]:
        """Initialize a fresh client with an unauthenticated CSRF token from PESU Academy."""
        logging.info("Fetching a new client with an unauthenticated CSRF token...")
        # Create a new client
        client = httpx2.AsyncClient(follow_redirects=True, timeout=10.0)
        self._metrics.increment(HTTP_CLIENTS, event="created")
        # On success the client is handed to the caller, so only close it if we fail to return it
        try:
            # Fetch the CSRF token
            async with _upstream_call(self._metrics, "csrf_fetch") as sink:
                resp = await client.get("https://www.pesuacademy.com/Academy/")
                sink.append(resp)
            soup = await asyncio.to_thread(HTMLParser, resp.text)
            if node := soup.css_first("meta[name='csrf-token']"):
                csrf_token = node.attributes["content"]
                logging.info(f"Fetched CSRF token: {csrf_token}")
                return client, csrf_token
            raise CSRFTokenError("CSRF token not found in the pre-authentication response.")
        except BaseException:
            await _close_client_quietly(client, self._metrics)
            raise

    async def _prefetch_client_with_csrf_token(self) -> None:
        """Prefetch a new client with an unauthenticated CSRF token.

        This method is used to prefetch a new client with an unauthenticated CSRF token.
        It is used to avoid the overhead of fetching a new client with an unauthenticated CSRF token
        for each request.
        """
        logging.info("Prefetching a new client with an unauthenticated CSRF token...")
        client, token = await self._fetch_new_client_with_csrf_token()
        # Until the new client is cached nothing else can reach it, so close it if we never get there
        # (for example if this task is cancelled while waiting for the lock during shutdown)
        try:
            async with self._csrf_lock:
                # Close old cached client (if any) to avoid leaks. A failure to close the old
                # client must not stop the refresh, so it is logged rather than raised.
                if self._client is not None:
                    await _close_client_quietly(self._client, self._metrics)
                # Store the new cached client/token
                self._client = client
                self._csrf_token = token
        except BaseException:
            await _close_client_quietly(client, self._metrics)
            raise
        logging.info("Cache refreshed with new unauthenticated CSRF token.")

    async def _get_client_with_csrf_token(self) -> tuple[httpx2.AsyncClient, str]:
        """Get the client with the cached CSRF token.

        This method is used to get the client with the cached CSRF token.
        It is used to avoid the overhead of fetching a new client with an unauthenticated CSRF token
        for each request.
        """
        async with self._csrf_lock:
            # Take the cached client/token for *this* request, if the cache is warm, and clear
            # the cache immediately so the next caller cannot reuse them
            cached = self._client is not None and self._csrf_token is not None
            if cached:
                client_to_use, token_to_use = self._client, self._csrf_token
                self._client = None
                self._csrf_token = None

        # Hit rate is the whole point of the prefetch: a cold cache means the caller waits on an
        # upstream round trip it was supposed to be spared.
        self._metrics.increment(CSRF_CACHE, outcome="hit" if cached else "miss")

        if not cached:
            # Cold cache: fetch *outside* the lock. Holding it across a fetch would queue every
            # concurrent request behind a 10s upstream timeout, and would not save any work --
            # each caller needs its own client, so they were already fetching one apiece, just
            # one at a time.
            client_to_use, token_to_use = await self._fetch_new_client_with_csrf_token()

        # Kick off async prefetch for the *next* request (non-blocking)
        self._spawn_prefetch_task()
        # Return a dedicated client/token for this request
        return client_to_use, token_to_use

    def _on_prefetch_task_done(self, task: asyncio.Task[None]) -> None:
        """Drop the finished prefetch task's reference and log any failure.

        Retrieving the exception is what keeps a failed prefetch from being reported only as
        "Task exception was never retrieved" when the task is garbage collected. A failed prefetch
        is not fatal: the cache stays empty and the next request fetches a client inline instead.

        Args:
            task (asyncio.Task[None]): The prefetch task that has completed.
        """
        self._prefetch_tasks.discard(task)
        # exception() raises on a cancelled task, so that has to be checked first
        if task.cancelled():
            self._metrics.increment(PREFETCH_TASKS, outcome="cancelled")
            return
        if (exception := task.exception()) is not None:
            self._metrics.increment(PREFETCH_TASKS, outcome="failure")
            logging.error(
                f"Background CSRF token prefetch failed: {exception!r}",
                exc_info=exception,
            )
        else:
            self._metrics.increment(PREFETCH_TASKS, outcome="success")

    def _spawn_prefetch_task(self) -> None:
        """Start a background prefetch of the next client and CSRF token."""
        task = asyncio.create_task(self._prefetch_client_with_csrf_token())
        # Hold a strong reference so the task cannot be garbage collected mid-flight
        self._prefetch_tasks.add(task)
        task.add_done_callback(self._on_prefetch_task_done)

    def _extract_and_update_profile(self, node: Node, idx: int, profile: dict) -> None:
        """Extract the profile data from a node and update the profile dictionary.

        Args:
            node (Node): Pre-parsed node containing the profile information
            idx (int): Index of the node
            profile (dict): The profile dictionary to update in-place
        """
        # Use the selector `label.lbl-title-light` to find the key label
        if not (key_node := node.css_first("label.lbl-title-light")) or not (key := key_node.text(strip=True)):
            self._metrics.increment(PROFILE_PARSE_ERRORS, reason="key_missing")
            raise ProfileParseError(f"Could not parse key for field at index {idx}.")
        # Use the adjacent sibling selector `+` to find value label
        if not (value_node := node.css_first("label.lbl-title-light + label")) or not (
            value := value_node.text(strip=True)
        ):
            self._metrics.increment(PROFILE_PARSE_ERRORS, reason="value_missing")
            raise ProfileParseError(f"Could not parse value for field at index {idx}.")
        logging.debug(f"Extracted key: '{key}' with value: '{value}' at index {idx}.")
        # If the key is in the map, add it to the profile
        if mapped_key := self.PROFILE_PAGE_HEADER_TO_KEY_MAP.get(key):
            logging.debug(f"Adding key: '{mapped_key}', value: '{value}' to profile...")
            profile[mapped_key] = value
        else:
            self._metrics.increment(PROFILE_PARSE_ERRORS, reason="unknown_field")
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
        """Close the cached client and stop any prefetch still in flight.

        The prefetches are cancelled first. Without that, one can complete *after* the cached
        client has been closed and quietly cache a fresh client that nobody ever closes.
        Cancelling is safe rather than leaky because both prefetch stages close their own client
        if they are interrupted before it reaches the cache.
        """
        # Snapshot once: the done callbacks mutate the set as the tasks finish
        tasks = tuple(self._prefetch_tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        async with self._csrf_lock:
            if self._client is not None:
                await _close_client_quietly(self._client, self._metrics)
                self._client = None
                self._csrf_token = None

    async def is_csrf_cache_ready(self) -> bool:
        """Report whether a cached unauthenticated CSRF client/token pair is available."""
        async with self._csrf_lock:
            return self._client is not None and self._csrf_token is not None

    async def get_profile_information(
        self,
        client: httpx2.AsyncClient,
        username: str,
    ) -> dict[str, Any]:
        """Get the profile information of the user.

        Args:
            client (httpx2.AsyncClient): The HTTP client to use for making requests.
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
        async with _upstream_call(self._metrics, "profile_fetch") as sink:
            response = await client.get(profile_url, params=query)
            sink.append(response)
        # If the status code is not 200, raise an exception because the profile page is not accessible
        if response.status_code != 200:
            raise ProfileFetchError(
                f"Failed to fetch student profile page from PESU Academy for user={username}.",
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
            self._metrics.increment(PROFILE_PARSE_ERRORS, reason="page_structure")
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
            profile["campusCode"] = int(campus_code)
            if campus_code == "1":
                profile["campus"] = "RR"
            elif campus_code == "2":
                profile["campus"] = "EC"
            else:
                # Not fatal -- the profile is returned without a campus name -- but it means the PRN
                # format has changed, which nothing else would surface.
                self._metrics.increment(PROFILE_PARSE_ERRORS, reason="unknown_campus_code")
                logging.warning(
                    f"Unknown campus code: {campus_code} parsed from PRN={profile['prn']} for user={username}",
                )

        # Check if we extracted any profile data
        if not profile:
            self._metrics.increment(PROFILE_PARSE_ERRORS, reason="no_data")
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

        logging.info(
            f"Connecting to PESU Academy with user={username}, profile={profile}, fields={fields} ...",
        )

        # Get a pre-fetched csrf token and client
        client, csrf_token = await self._get_client_with_csrf_token()
        # This client belongs to this request, so close it on every exit path, not just success
        try:
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
            async with _upstream_call(self._metrics, "login") as sink:
                response = await client.post(auth_url, data=data)
                sink.append(response)
            soup = await asyncio.to_thread(HTMLParser, response.text)
            logging.debug("Authentication response received.")

            # If class login-form is present, login failed
            if soup.css_first("div.login-form"):
                # Log the error and return the error message
                raise AuthenticationError(
                    f"Invalid username or password, or user does not exist for user={username}.",
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
                    f"CSRF token not found in the post-authentication response for user={username}.",
                )

            result = {"status": status, "message": "Login successful."}

            if profile:
                logging.info(f"Profile data requested for user={username}. Fetching profile data...")
                # Fetch the profile information
                result["profile"] = await self.get_profile_information(client, username)
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
