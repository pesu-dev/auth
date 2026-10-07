# pesu-auth

[![CI Checks](https://img.shields.io/github/actions/workflow/status/pesu-dev/auth/ci_checks.yml?branch=dev&label=CI%20Checks)](https://github.com/pesu-dev/auth/actions/workflows/ci_checks.yml)
[![Deploy to Production](https://github.com/pesu-dev/auth/actions/workflows/deploy_prod.yml/badge.svg)](https://github.com/pesu-dev/auth/actions/workflows/deploy_prod.yml)
[![GHCR Image](https://img.shields.io/badge/GHCR-Docker%20Image-2496ED?logo=docker&logoColor=white)](https://github.com/pesu-dev/auth/pkgs/container/pesu-auth)

[![Docker Automated build](https://img.shields.io/docker/automated/pesudev/pesu-auth?logo=docker)](https://hub.docker.com/r/pesudev/pesu-auth/builds)
[![Docker Image Version (tag)](https://img.shields.io/docker/v/pesudev/pesu-auth/latest?logo=docker&label=build%20commit)](https://hub.docker.com/r/pesudev/pesu-auth/tags)
[![Docker Image Size (tag)](https://img.shields.io/docker/image-size/pesudev/pesu-auth/latest?logo=docker)](https://hub.docker.com/r/pesudev/pesu-auth)

A simple and lightweight API to authenticate PESU credentials using PESU Academy.

The API is secure and protects user privacy by not storing any user credentials. It only validates credentials and
returns the user's profile information. No personal data is stored.

### How it works

PESUAuth signs in to [PESU Academy](https://www.pesuacademy.com/) on the user's behalf, through the same API that the
PESU Academy mobile app uses:

1. The username and password are sent to PESU Academy's login endpoint. If PESU Academy accepts them, the request
   succeeds; if it rejects them, PESUAuth answers `401`.
1. If the profile was requested, a second call fetches it with the access token that the login returned, and the result
   is mapped into the [`ProfileObject`](#profileobject) described below.

Credentials are only ever sent to PESU Academy, over HTTPS. The password is never stored or logged, and neither is the
access token PESU Academy issues. Every request uses its own connection to PESU Academy, closed before PESUAuth
responds, so nothing from one user's sign-in is shared with another's.

> [!NOTE]
> PESU Academy's mobile API is not publicly documented and can change without notice. If it does, `/authenticate`
> may answer `422` or `502` until PESUAuth is updated to match.

## PESUAuth LIVE Deployment

[![Production API version](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fpesuauth.onrender.com%2Fopenapi.json&query=%24.info.version&label=production&color=blue&prefix=v&cacheSeconds=120)](https://pesuauth.onrender.com/)
[![Staging API version](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fpesuauth-dev.onrender.com%2Fopenapi.json&query=%24.info.version&label=staging&color=orange&prefix=v&cacheSeconds=120)](https://pesuauth-dev.onrender.com/)

- You can access the PESUAuth API endpoints [here](https://pesuauth.onrender.com/).
- You can view the health status of the API on the health check pages for
  [production](https://xzlk85cp.status.cron-job.org) and [staging](https://6ns95sgb.status.cron-job.org).
- You can view detailed metrics and KPIs for both environments on the
  [PESUAuth metrics dashboard](https://loyalplateau1250.grafana.net/public-dashboards/bd1df85e9420490f88978906b0d9fbdf),
  built from the counters that [`/metrics`](#metrics) exposes.

#### API Status

| **Environment** | **Check**                        | **Status**                                                                                                                                                                                           |
| --------------- | -------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Production      | Docs                             | ![Docs](https://api.cron-job.org/jobs/4424640/69701a6f8df1d307/status-7.svg)                                                                                                                         |
| Production      | Health                           | ![Health](https://api.cron-job.org/jobs/6338038/9feb0f217be714ec/status-7.svg)                                                                                                                       |
| Production      | Authentication                   | ![Authentication](https://api.cron-job.org/jobs/5672615/1d744f1dc18fb505/status-7.svg)                                                                                                               |
| Production      | Authentication with Profile Data | ![Authentication with profile](https://api.cron-job.org/jobs/4424663/d5a30351867acec9/status-7.svg)                                                                                                  |
| Staging         | Docs                             | ![Docs](https://api.cron-job.org/jobs/6382167/bc84078c3b85999c/status-7.svg)                                                                                                                         |
| Staging         | Health                           | ![Health](https://api.cron-job.org/jobs/6382168/e38759ed59c0d9c1/status-7.svg)                                                                                                                       |
| Staging         | Authentication                   | ![Authentication](https://api.cron-job.org/jobs/6382175/226ee5764400bf01/status-7.svg)                                                                                                               |
| Staging         | Authentication with Profile Data | ![Authentication with profile](https://api.cron-job.org/jobs/6382173/5cff341ab10ab962/status-7.svg)                                                                                                  |
|                 | Detailed metrics and KPIs        | [![Grafana](https://img.shields.io/badge/Grafana-metrics%20%26%20KPIs-F46800?logo=grafana&logoColor=white)](https://loyalplateau1250.grafana.net/public-dashboards/bd1df85e9420490f88978906b0d9fbdf) |

> [!NOTE]
> All timestamps are in UTC.

> [!WARNING]
> Both environments are hosted on free tier servers located in Singapore. As a result, you *might* experience higher latencies and slower response times, compared to running the API locally or on a server closer to your location.

## How to run PESUAuth locally

Running the PESUAuth API locally is simple. Clone the repository and follow the steps below to get started.

> [!TIP]
> We recommend running the API locally using Docker for ease of use, the best performance, and lowest latency.

### Running with Docker

This is the easiest and recommended way to run the API locally. Ensure you have Docker installed on your system. Run the
following commands to start the API.

> [!NOTE]
> For security, the container runs as an unprivileged user (`UID 10001:10001`) with read-only application files.

1. Build the Docker image either from the source code or pull the pre-built image from Docker Hub.

   1. You can build the Docker image from the source code by running the following command in the root directory of
      the repository.

      ```bash
      docker build . --tag pesu-auth
      ```

   1. You can also pull the pre-built Docker image
      from [Docker Hub](https://hub.docker.com/repository/docker/pesudev/pesu-auth/general) by running the
      following command:

      ```bash
      docker pull pesudev/pesu-auth:latest
      ```

1. Run the Docker container

   ```bash
   docker run --name pesu-auth -d -p 5000:5000 pesu-auth
   # If you pulled the pre-built image, use the following command instead:
   docker run --name pesu-auth -d -p 5000:5000 pesudev/pesu-auth:latest
   ```

1. Access the API at `http://localhost:5000/`

### Running without Docker

If you don't have Docker installed, you can run the API natively. Ensure you have Python 3.14 or higher
installed on your system. We recommend using a package manager like [`uv`](https://docs.astral.sh/uv/) to manage
dependencies.

1. Create a virtual environment using and activate it. Then, install the dependencies using the following commands.

   ```bash
   uv venv --python=3.14
   source .venv/bin/activate
   uv sync
   ```

1. Run the API using the following command.

   ```bash
   uv run python -m app.app
   ```

   You can set the port with `--port` or `PORT`. The priority order is `--port`, then `PORT`, then the default of `5000`.

   ```bash
   PORT=8080 uv run python -m app.app
   ```

1. Access the API as previously mentioned on `http://localhost:5000/`

## How to use the PESUAuth API

The API provides multiple endpoints for authentication, documentation, and monitoring.

| **Endpoint**    | **Method** | **Description**                                        |
| --------------- | ---------- | ------------------------------------------------------ |
| `/`             | `GET`      | Serves the interactive API documentation (Swagger UI). |
| `/authenticate` | `POST`     | Authenticates a user using their PESU credentials.     |
| `/health`       | `GET`      | A health check endpoint to monitor the API's status.   |
| `/metrics`      | `GET`      | Exposes traffic and error counters. See `fmt` below.   |
| `/readme`       | `GET`      | Redirects to the project's official GitHub repository. |

### `/authenticate`

You can send a request to the `/authenticate` endpoint with the user's credentials and the API will return a JSON
object, with the user's profile information if requested.

#### Request Parameters

| **Parameter** | **Optional** | **Type**    | **Default** | **Description**                                                                                                                                                                                                     |
| ------------- | ------------ | ----------- | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `username`    | No           | `str`       |             | The user's SRN, PRN, email address, or phone number                                                                                                                                                                 |
| `password`    | No           | `str`       |             | The user's password. It is sent only to PESU Academy, and never stored or logged                                                                                                                                    |
| `profile`     | Yes          | `boolean`   | `False`     | Whether to fetch profile information. This makes a second call to PESU Academy, so it takes longer                                                                                                                  |
| `fields`      | Yes          | `list[str]` | `None`      | Which [`ProfileObject`](#profileobject) fields to return. Only used when `profile` is `true`. If not provided, all fields are returned. Fields come back in the table's order, whatever order they are asked for in |

The request body is validated strictly. A missing or empty `username` or `password`, one that is not valid text, a value of the wrong type (such as
the string `"true"` for `profile`), an unknown key, an empty `fields` list, or an unknown field name is rejected with a
`400`.

#### Responses

| **Code** | **When**                                                                                                                                                                |
| -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `200`    | The credentials are valid. `profile` is included if it was requested                                                                                                    |
| `400`    | The request body failed validation, as described above                                                                                                                  |
| `401`    | PESU Academy rejected the credentials: a wrong password, or a user that does not exist                                                                                  |
| `422`    | PESU Academy's profile response could not be parsed, or reported success without any `STUDENT_INFO`, which means their API changed. Only when the profile was requested |
| `500`    | An unexpected failure, rendered by the catch-all handler                                                                                                                |
| `502`    | PESU Academy could not be reached, timed out, or answered the login or profile request unexpectedly                                                                     |

Every error this API renders carries the same `{status, message, timestamp}` body, with `status` set to `false`. The
only exceptions are an unknown path or an unsupported method, which get the framework's own `404` or `405` with a
`{"detail": ...}` body.

#### Response Object

On authentication, it returns the following parameters in a JSON object. If the authentication was successful and
profile data was requested, the response's `profile` key will store a dictionary with a user's profile information.
**On an unsuccessful sign-in, this field will not exist**.

| **Field**   | **Type**        | **Description**                                                          |
| ----------- | --------------- | ------------------------------------------------------------------------ |
| `status`    | `boolean`       | A flag indicating whether the overall request was successful             |
| `profile`   | `ProfileObject` | A nested map storing the profile information, returned only if requested |
| `message`   | `str`           | A message that provides information corresponding to the status          |
| `timestamp` | `datetime`      | The time of the request, as an ISO 8601 timestamp in IST (`+05:30`)      |

##### `ProfileObject`

This object contains the user's profile information, which is returned only if the `profile` parameter is set to `True`.
If the authentication fails, this field will not be present in the response.

Only the fields in the table below can be requested; any other name in `fields` is a `400`. Every requested field is
present, and **any field can be `null`** when PESU Academy has no value for it, does not send it, or sends it in an
unexpected shape. For example, a student who has graduated has a `null` `semester` and `section`. A requested field is
never left out for having no value; only the fields not asked for in `fields` are, and fields come back in the order of
the table below.

Every field is taken from the `STUDENT_INFO` block of PESU Academy's profile response, as PESU Academy sends it, except
`campus` and `gender` (from `STUDENT_PHOTO`, since `STUDENT_INFO` does not have them) and `campusCode` (mapped from
`campus`). No other part of PESU Academy's responses stands in for a value its source lacks, so that field is `null`; a
successful profile response whose `STUDENT_INFO` is missing or holds no usable value is a `422`.

| **Field**         | **Type** | **Description**                                                                                                                                                                                                                                                 |
| ----------------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `name`            | `str`    | Full name of the user                                                                                                                                                                                                                                           |
| `prn`             | `str`    | PRN of the user: `PES`, the campus digit, the year of joining and a 5-digit number, such as `PES1202000001`                                                                                                                                                     |
| `srn`             | `str`    | SRN of the user: `PES`, the campus digit, the program (`UG`, `PG`, ...), the last two digits of the year of joining, the branch and a 3-digit number, such as `PES1UG20CS001`. For students who joined before SRNs were introduced, it is the same as their PRN |
| `program`         | `str`    | Academic program as PESU Academy writes it, such as `B.Tech.`; PESU Academy sends no full name.                                                                                                                                                                 |
| `branch`          | `str`    | Full name of the branch, such as `Computer Science and Engineering`                                                                                                                                                                                             |
| `semester`        | `str`    | Current semester, as PESU Academy writes it, such as `Sem-4`                                                                                                                                                                                                    |
| `section`         | `str`    | Current section, such as `Section C`                                                                                                                                                                                                                            |
| `email`           | `str`    | Email address registered with PESU                                                                                                                                                                                                                              |
| `mobile`          | `str`    | Mobile number registered with PESU                                                                                                                                                                                                                              |
| `campusCode`      | `int`    | `1` for `PES University (Ring Road)`, `2` for `PES University (Electronic City)`; `null` for any other campus name                                                                                                                                              |
| `campus`          | `str`    | Name of the campus's institute as PESU Academy writes it, such as `PES University (Ring Road)`                                                                                                                                                                  |
| `firstName`       | `str`    | First name of the user                                                                                                                                                                                                                                          |
| `middleName`      | `str`    | Middle name of the user, or `null` if they have none                                                                                                                                                                                                            |
| `lastName`        | `str`    | Last name of the user                                                                                                                                                                                                                                           |
| `branchShortCode` | `str`    | Abbreviation of the branch, such as `CSE`                                                                                                                                                                                                                       |
| `gender`          | `str`    | Gender of the user, as recorded by PESU                                                                                                                                                                                                                         |
| `dateOfBirth`     | `str`    | Date of birth, as `YYYY-MM-DD`                                                                                                                                                                                                                                  |

Everything else in PESU Academy's responses, such as the photo, blood group, addresses, parents' details and marks, is
discarded and never returned, and cannot be requested in `fields`.

### `/health`

Answers `200` whenever the process is serving; a `500` would come from the catch-all handler, as on any other endpoint.

This endpoint can be used to check the health of the API. It's useful for monitoring and uptime checks. This endpoint
does not take any request parameters.

#### Response Object

| **Field**   | **Type**   | **Description**                                                     |
| ----------- | ---------- | ------------------------------------------------------------------- |
| `status`    | `boolean`  | `true` if healthy, `false` if there was an error                    |
| `message`   | `str`      | "ok" if healthy, error message otherwise                            |
| `timestamp` | `datetime` | A timezone offset timestamp indicating the time of the health check |

### `/metrics`

This endpoint exposes counters describing the traffic this process has served and the work it did to serve it. It takes
no request parameters other than the format selector below. It is open by default and can be put behind a bearer token
— see [Protecting the endpoint](#protecting-the-endpoint).

#### Query Parameters

| **Field** | **Type** | **Description**                                                                        |
| --------- | -------- | -------------------------------------------------------------------------------------- |
| `fmt`     | `str`    | `prometheus` (default) for the text exposition format, or `json` for the same counters |

The default is `prometheus` because that is what a scraper pointed at this path expects. An unrecognised value is a
`400`, like any other validation failure.

```bash
curl http://localhost:5000/metrics                  # Prometheus text, for a scraper
curl http://localhost:5000/metrics?fmt=json | jq    # the same numbers, for a human
```

#### Responses

| **Code** | **When**                                                                                   |
| -------- | ------------------------------------------------------------------------------------------ |
| `200`    | The counters, in the format named by `fmt`                                                 |
| `400`    | `fmt` was something other than `prometheus` or `json`                                      |
| `401`    | A token is configured and the request did not carry it. Carries `WWW-Authenticate: Bearer` |
| `500`    | An unexpected failure, rendered by the catch-all handler like on any other endpoint        |

#### How collection works

Everything is counted **in this process, in memory**. There is no database and no external dependency, and the counters
**reset to zero when the process restarts** — which on the hosted environments is often. `processStartTimeSeconds` is
exposed so a dashboard can tell a restart apart from a drop in traffic.

Collection happens at three layers, and which layer records what is deliberate:

| Layer                  | What it records                                                 | Why there                                                                                                                                                                                        |
| ---------------------- | --------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **HTTP middleware**    | request counts, status codes, matched route, latency, in-flight | It is the only place that sees every request, including ones that never reach a route                                                                                                            |
| **Exception handlers** | the error's exception class                                     | The middleware sees a status code; only the handler knows which class produced it. `UpstreamError` and `ProfileFetchError` are both `502`, and the class is the only thing that tells them apart |
| **`app/pesu.py`**      | upstream calls, client lifecycle, profile parsing               | These are not HTTP requests to this API at all, so nothing above could see them                                                                                                                  |

The middleware and the handlers write to **different metric families**, so a single failed request contributes exactly
one status sample and exactly one error sample — never two of either.

Two accounting rules hold at all times, and are the quickest way to tell whether the numbers are trustworthy:

```
requests.success + requests.failed + requestsInFlight  ==  requests.total
sum(responsesByStatus)                                 ==  requests.success + requests.failed
```

A login failure's *reason* comes from `errorsByType`, which names the exception class.
`authenticationResults` carries only the outcome, so the reason is recorded in exactly one place, and
`sum(authenticationResults) == authentication.total` modulo attempts still in flight.

`sum(errorsByType)` is normally **less** than `requests.failed`: a `404` or `405` is produced by the router, so no
exception handler of ours runs for it.

A few definitions that are easy to assume wrongly:

- **Latency is time to response *start***, not full request duration. The middleware measures up to the point the
  response begins; the body streams afterwards. It uses a monotonic clock, so an NTP correction cannot corrupt the sum.
- **Success means a status below 400**, not below 300. `/readme` answers `308`, and that is the endpoint working.
- **Summaries expose `_sum` and `_count`, not quantiles.** Compute a mean with
  `rate(pesu_auth_request_latency_seconds_sum[5m]) / rate(pesu_auth_request_latency_seconds_count[5m])`.
- **Scrapes of `/metrics` count themselves.** Excluding them would break the accounting rules above; subtract
  `pesu_auth_route_requests_total{route="/metrics"}` if you need traffic without them.
- **A cancelled request is not recorded as an outcome.** If a caller disconnects, `requests.total` has already counted
  it but no status ever exists, so `total` legitimately exceeds `success + failed + inFlight` by the number abandoned.

#### What each metric means

**Traffic**

| Metric                                | Meaning                                                                                                                                                                                 |
| ------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `requests_total`                      | Requests received, counted on arrival                                                                                                                                                   |
| `requests_success_total`              | Answered with a status below 400                                                                                                                                                        |
| `requests_failed_total`               | Answered with a status of 400 or above                                                                                                                                                  |
| `requests_in_flight`                  | Received but not yet answered. A gauge; it is what explains the gap in the totals                                                                                                       |
| `responses_total{status}`             | Responses by HTTP status code                                                                                                                                                           |
| `route_requests_total{method,route}`  | Requests by matched route template and method. Never the raw path, so an unmatched path becomes `<unmatched>` rather than a new series per probe, and an unknown verb becomes `<other>` |
| `request_latency_seconds`             | Time to response start, all routes                                                                                                                                                      |
| `route_latency_seconds{method,route}` | The same, per route                                                                                                                                                                     |

**Failures**

| Metric                           | Meaning                                                                                                                                                                                                    |
| -------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `failures_total{fault}`          | Failed requests by whose fault it was: `client` for 4xx, `server` for 5xx. Alert on `server` without enumerating status codes                                                                              |
| `errors_total{type}`             | Errors rendered by an exception handler, by exception class: `AuthenticationError`, `UpstreamError`, `ProfileFetchError`, `ProfileParseError`, `RequestValidationError`, or whatever reached the catch-all |
| `validation_errors_total{field}` | Request validation failures by the field that failed. Unrecognised keys collapse into `other`, since the request body is caller-controlled                                                                 |

**Authentication**

| Metric                                   | Meaning                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| ---------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `authentication_requests_total{profile}` | Authentication requests, split by whether profile data was asked for                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| `authentication_results_total{result}`   | Attempts by outcome: `success` or `failure`. Deliberately only those two — `errors_total` already names the exception class, and recording the reason here too would put one fact in two places. This family exists for the login **success rate**, where success and failure share a denominator                                                                                                                                                                                                                                                                                                                                                                                       |
| `profile_field_filtering_total{enabled}` | Profile fetches, split by whether the caller narrowed the returned fields. Recorded where the branch is taken, so a caller passing exactly the default list counts as `false`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| `profile_parse_errors_total{reason}`     | Profile response problems by what broke: `response_structure` (the response could not be parsed, a `422`), `unknown_campus_code` (a campus name with no known campus code), `missing_field` (a field PESU Academy did not send at all) and `unexpected_value` (a field sent in an unexpected shape). The last two are counted once per field, returned to the caller as `null`, and named in the log. `response_structure`, `missing_field` and `unexpected_value` mean PESU Academy's API changed; `unknown_campus_code` usually means a new campus, or a new way of writing a campus's name. A field PESU Academy sends with no value is not counted: that is a student with no value |

**Upstream (PESU Academy)**

PESU Academy is the only dependency this service has, and the only thing that can be slow or down. Its latency is
measured separately from the API's own, so a slow request can be attributed rather than guessed at. Two operations,
both calls to PESU Academy's mobile API: `login`, and `profile_fetch` (made only when a profile is requested).

| Metric                                       | Meaning                                                                                                                                                              |
| -------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `upstream_requests_total{operation,outcome}` | Calls by outcome: `success`, `error` (raised, including timeouts), `cancelled` (we walked away — a disconnect or a shutdown, deliberately *not* counted as an error) |
| `upstream_responses_total{operation,status}` | The status code PESU Academy returned                                                                                                                                |
| `upstream_latency_seconds{operation}`        | Seconds spent waiting on each operation                                                                                                                              |

A wrong password counts as a **successful** `login` call: PESU answered, with a `401`. The call worked; the
credentials did not. Likewise a profile response we cannot parse is a successful `profile_fetch` — the fetch worked and
our parsing of it did not.

**Internals**

| Metric                         | Meaning                                                                                                                                                                                                      |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `http_clients_total{event}`    | `created`, `closed`, `close_failed`. **`created` minus `closed` is how many are still open**, which should be `0` at rest — each login closes its own client. A number that climbs is a connection-pool leak |
| `lifespan_events_total{event}` | `startup` and `shutdown` seen by this process                                                                                                                                                                |
| `process_start_time_seconds`   | Start time since the Unix epoch. A gauge, so restarts are visible                                                                                                                                            |

#### Prometheus response

<details>
<summary>Full example (<code>fmt=prometheus</code>)</summary>

```
# HELP pesu_auth_requests_total HTTP requests received.
# TYPE pesu_auth_requests_total counter
pesu_auth_requests_total 1284
# HELP pesu_auth_requests_success_total HTTP requests answered with a status below 400.
# TYPE pesu_auth_requests_success_total counter
pesu_auth_requests_success_total 1102
# HELP pesu_auth_requests_failed_total HTTP requests answered with a status of 400 or above.
# TYPE pesu_auth_requests_failed_total counter
pesu_auth_requests_failed_total 181
# HELP pesu_auth_responses_total HTTP responses, by status code.
# TYPE pesu_auth_responses_total counter
pesu_auth_responses_total{status="200"} 1094
pesu_auth_responses_total{status="308"} 8
pesu_auth_responses_total{status="400"} 12
pesu_auth_responses_total{status="401"} 160
pesu_auth_responses_total{status="500"} 4
pesu_auth_responses_total{status="502"} 5
# HELP pesu_auth_route_requests_total HTTP requests, by matched route and method.
# TYPE pesu_auth_route_requests_total counter
pesu_auth_route_requests_total{method="GET",route="/"} 8
pesu_auth_route_requests_total{method="GET",route="/health"} 302
pesu_auth_route_requests_total{method="GET",route="/metrics"} 180
pesu_auth_route_requests_total{method="GET",route="/readme"} 8
pesu_auth_route_requests_total{method="POST",route="/authenticate"} 786
# HELP pesu_auth_errors_total Errors rendered by an exception handler, by exception class.
# TYPE pesu_auth_errors_total counter
pesu_auth_errors_total{type="AuthenticationError"} 160
pesu_auth_errors_total{type="ProfileFetchError"} 3
pesu_auth_errors_total{type="RequestValidationError"} 12
pesu_auth_errors_total{type="RuntimeError"} 4
pesu_auth_errors_total{type="UpstreamError"} 2
# HELP pesu_auth_authentication_requests_total Authentication requests, by whether profile data was requested.
# TYPE pesu_auth_authentication_requests_total counter
pesu_auth_authentication_requests_total{profile="false"} 640
pesu_auth_authentication_requests_total{profile="true"} 134
# HELP pesu_auth_authentication_results_total Authentication attempts, by outcome. errors_total says why one failed.
# TYPE pesu_auth_authentication_results_total counter
pesu_auth_authentication_results_total{result="failure"} 169
pesu_auth_authentication_results_total{result="success"} 604
# HELP pesu_auth_profile_field_filtering_total Profile fetches, by whether the caller narrowed the fields returned.
# TYPE pesu_auth_profile_field_filtering_total counter
pesu_auth_profile_field_filtering_total{enabled="false"} 90
pesu_auth_profile_field_filtering_total{enabled="true"} 40
# HELP pesu_auth_profile_parse_errors_total Profile problems, keyed by what was missing, unreadable or unmapped.
# TYPE pesu_auth_profile_parse_errors_total counter
pesu_auth_profile_parse_errors_total{reason="unknown_campus_code"} 3
# HELP pesu_auth_validation_errors_total Request validation failures, by the field that failed.
# TYPE pesu_auth_validation_errors_total counter
pesu_auth_validation_errors_total{field="password"} 4
pesu_auth_validation_errors_total{field="username"} 8
# HELP pesu_auth_failures_total Failed requests, by whose fault it was: the caller's (4xx) or ours (5xx).
# TYPE pesu_auth_failures_total counter
pesu_auth_failures_total{fault="client"} 172
pesu_auth_failures_total{fault="server"} 9
# HELP pesu_auth_request_latency_seconds Seconds from receiving a request to starting its response.
# TYPE pesu_auth_request_latency_seconds summary
pesu_auth_request_latency_seconds_sum 1651.761
pesu_auth_request_latency_seconds_count 1283
# HELP pesu_auth_route_latency_seconds Seconds from receiving a request to starting its response, by route.
# TYPE pesu_auth_route_latency_seconds summary
pesu_auth_route_latency_seconds_sum{method="GET",route="/"} 0.08
pesu_auth_route_latency_seconds_sum{method="GET",route="/health"} 0.413
pesu_auth_route_latency_seconds_sum{method="GET",route="/metrics"} 0.36
pesu_auth_route_latency_seconds_sum{method="GET",route="/readme"} 0.008
pesu_auth_route_latency_seconds_sum{method="POST",route="/authenticate"} 1650.9
pesu_auth_route_latency_seconds_count{method="GET",route="/"} 8
pesu_auth_route_latency_seconds_count{method="GET",route="/health"} 302
pesu_auth_route_latency_seconds_count{method="GET",route="/metrics"} 180
pesu_auth_route_latency_seconds_count{method="GET",route="/readme"} 8
pesu_auth_route_latency_seconds_count{method="POST",route="/authenticate"} 785
# HELP pesu_auth_upstream_requests_total Requests made to PESU Academy, by operation and outcome.
# TYPE pesu_auth_upstream_requests_total counter
pesu_auth_upstream_requests_total{operation="login",outcome="error"} 2
pesu_auth_upstream_requests_total{operation="login",outcome="success"} 771
pesu_auth_upstream_requests_total{operation="profile_fetch",outcome="error"} 1
pesu_auth_upstream_requests_total{operation="profile_fetch",outcome="success"} 132
# HELP pesu_auth_upstream_responses_total Responses from PESU Academy, by operation and status code.
# TYPE pesu_auth_upstream_responses_total counter
pesu_auth_upstream_responses_total{operation="login",status="200"} 611
pesu_auth_upstream_responses_total{operation="login",status="401"} 160
pesu_auth_upstream_responses_total{operation="profile_fetch",status="200"} 130
pesu_auth_upstream_responses_total{operation="profile_fetch",status="502"} 2
# HELP pesu_auth_upstream_latency_seconds Seconds spent waiting on PESU Academy, by operation.
# TYPE pesu_auth_upstream_latency_seconds summary
pesu_auth_upstream_latency_seconds_sum{operation="login"} 1586.7
pesu_auth_upstream_latency_seconds_sum{operation="profile_fetch"} 53.2
pesu_auth_upstream_latency_seconds_count{operation="login"} 773
pesu_auth_upstream_latency_seconds_count{operation="profile_fetch"} 133
# HELP pesu_auth_http_clients_total Upstream HTTP client lifecycle. created minus closed is how many are still open.
# TYPE pesu_auth_http_clients_total counter
pesu_auth_http_clients_total{event="closed"} 773
pesu_auth_http_clients_total{event="created"} 774
# HELP pesu_auth_lifespan_events_total Application lifespan events, by kind.
# TYPE pesu_auth_lifespan_events_total counter
pesu_auth_lifespan_events_total{event="startup"} 1
# HELP pesu_auth_requests_in_flight Requests received but not yet answered.
# TYPE pesu_auth_requests_in_flight gauge
pesu_auth_requests_in_flight 1
# HELP pesu_auth_process_start_time_seconds Start time of the process since the Unix epoch, in seconds.
# TYPE pesu_auth_process_start_time_seconds gauge
pesu_auth_process_start_time_seconds 1757660400.12
```

</details>

#### JSON response

The same numbers, with labels folded into object keys — `responsesByStatus` keyed by status code, `requestsByRoute` by
`"METHOD route-template"`, `errorsByType` by exception class. Latency objects add a pre-computed `averageSeconds`,
which is `null` rather than absent when nothing has been recorded yet, so the shape is stable.

<details>
<summary>Full example (<code>fmt=json</code>)</summary>

```json
{
  "startTimeSeconds": 1757660400.12,
  "uptimeSeconds": 86400.0,
  "requests": {
    "total": 1284,
    "success": 1102,
    "failed": 181
  },
  "latency": {
    "sumSeconds": 1651.761,
    "count": 1283,
    "averageSeconds": 1.2874208885424785
  },
  "authentication": {
    "total": 774,
    "withProfile": 134,
    "withoutProfile": 640
  },
  "responsesByStatus": {
    "200": 1094,
    "308": 8,
    "400": 12,
    "401": 160,
    "500": 4,
    "502": 5
  },
  "requestsByRoute": {
    "GET /": {
      "requests": 8,
      "latency": {
        "sumSeconds": 0.08,
        "count": 8,
        "averageSeconds": 0.01
      }
    },
    "GET /health": {
      "requests": 302,
      "latency": {
        "sumSeconds": 0.413,
        "count": 302,
        "averageSeconds": 0.0013675496688741722
      }
    },
    "GET /metrics": {
      "requests": 180,
      "latency": {
        "sumSeconds": 0.36,
        "count": 180,
        "averageSeconds": 0.002
      }
    },
    "GET /readme": {
      "requests": 8,
      "latency": {
        "sumSeconds": 0.008,
        "count": 8,
        "averageSeconds": 0.001
      }
    },
    "POST /authenticate": {
      "requests": 786,
      "latency": {
        "sumSeconds": 1650.9,
        "count": 785,
        "averageSeconds": 2.1030573248407642
      }
    }
  },
  "errorsByType": {
    "AuthenticationError": 160,
    "ProfileFetchError": 3,
    "RequestValidationError": 12,
    "RuntimeError": 4,
    "UpstreamError": 2
  },
  "requestsInFlight": 1,
  "failuresByFault": {
    "client": 172,
    "server": 9
  },
  "validationErrorsByField": {
    "password": 4,
    "username": 8
  },
  "authenticationResults": {
    "failure": 169,
    "success": 604
  },
  "profileFieldFiltering": {
    "false": 90,
    "true": 40
  },
  "profileParseErrors": {
    "unknown_campus_code": 3
  },
  "upstream": {
    "login": {
      "success": 771,
      "error": 2,
      "cancelled": 0,
      "latency": {
        "sumSeconds": 1586.7,
        "count": 773,
        "averageSeconds": 2.0526520051746444
      },
      "responsesByStatus": {
        "200": 611,
        "401": 160
      }
    },
    "profile_fetch": {
      "success": 132,
      "error": 1,
      "cancelled": 0,
      "latency": {
        "sumSeconds": 53.2,
        "count": 133,
        "averageSeconds": 0.4
      },
      "responsesByStatus": {
        "200": 130,
        "502": 2
      }
    }
  },
  "httpClients": {
    "closed": 773,
    "created": 774
  },
  "lifespanEvents": {
    "startup": 1
  }
}
```

</details>

#### Protecting the endpoint

`/metrics` is **open unless a token is configured**, through the `METRICS_TOKEN` environment
variable.

| `METRICS_TOKEN` | Behaviour of `/metrics`                                                |
| --------------- | ---------------------------------------------------------------------- |
| unset           | Open. A credential sent anyway is **ignored, not rejected**            |
| blank           | Same as unset — an empty value means "no token", not "the empty token" |
| set             | Every request must carry that token, in both formats                   |

```bash
# Deployed: an environment variable on the service
docker run --name pesu-auth -d -p 5000:5000 -e METRICS_TOKEN=<token> pesu-auth

# Running from source: pass it to the process
METRICS_TOKEN=<token> uv run python -m app.app
```

`.env` is read by the test suite, never by the application, so a token there does not protect a
running server.

A rejection carries `WWW-Authenticate: Bearer` and the same error body as every other failure.

```bash
curl http://localhost:5000/metrics                                   # 401
curl -H "Authorization: Bearer <token>" http://localhost:5000/metrics  # 200
```

The interactive docs at `/` carry an **Authorize** button for it. Paste the token there with no
`Bearer ` prefix; Swagger adds that itself.

The variable is read once at startup, so changing it needs a restart. No other endpoint is
affected — `/health` in particular stays open, since uptime monitors and the hosting platform's own
health check send no credentials.

#### Scraping the endpoint

The default format is the Prometheus text exposition format precisely so that a scraper pointed at
this path needs no configuration. Any Prometheus-compatible collector works:

```yaml
scrape_configs:
  - job_name: pesu-auth
    metrics_path: /metrics
    scheme: https
    static_configs:
      - targets: [ "pesuauth.onrender.com" ]
    authorization:
      credentials: <token>   # omit when METRICS_TOKEN is unset
```

### `/readme`

This endpoint redirects to the project's official GitHub repository with a `308`, and takes no request parameters. A `500` would come from the catch-all handler, as on any other endpoint.

### Integrating your application with the PESUAuth API

Here are some examples of how you can integrate your application with the PESUAuth API using Python and cURL.

#### Python

##### Request

```python
import requests

data = {
    "username": "your SRN, PRN, email or phone number here",
    "password": "your password here",
    "profile": True,  # Optional, defaults to False
}

response = requests.post("http://localhost:5000/authenticate", json=data)
print(response.json())
```

##### Response

```json
{
  "status": true,
  "profile": {
    "name": "John Doe",
    "prn": "PES1202000001",
    "srn": "PES1UG20CS001",
    "program": "B.Tech.",
    "branch": "Computer Science and Engineering",
    "semester": "Sem-4",
    "section": "Section C",
    "email": "johndoe@gmail.com",
    "mobile": "1234567890",
    "campusCode": 1,
    "campus": "PES University (Ring Road)",
    "firstName": "John",
    "middleName": null,
    "lastName": "Doe",
    "branchShortCode": "CSE",
    "gender": "Male",
    "dateOfBirth": "2002-01-31"
  },
  "message": "Login successful.",
  "timestamp": "2024-07-28T22:30:10.103368+05:30"
}
```

#### cURL

##### Request

```bash
curl -X POST http://localhost:5000/authenticate \
-H "Content-Type: application/json" \
-d '{
    "username": "your SRN, PRN, email or phone number here",
    "password": "your password here"
}'
```

##### Response

```json
{
  "status": true,
  "message": "Login successful.",
  "timestamp": "2024-07-28T22:30:10.103368+05:30"
}
```

#### Requesting specific fields

Pass `fields` to receive only some of the profile, in any order; they come back in the order of the table above. A
requested field that the user has no value for is `null` — here, a student who has graduated and has no middle
name.

```bash
curl -X POST http://localhost:5000/authenticate \
-H "Content-Type: application/json" \
-d '{
    "username": "your SRN, PRN, email or phone number here",
    "password": "your password here",
    "profile": true,
    "fields": ["name", "srn", "semester", "campus", "middleName", "mobile"]
}'
```

```json
{
  "status": true,
  "message": "Login successful.",
  "timestamp": "2024-07-28T22:30:10.103368+05:30",
  "profile": {
    "name": "John Doe",
    "srn": "PES1UG20CS001",
    "semester": null,
    "mobile": "1234567890",
    "campus": "PES University (Ring Road)",
    "middleName": null
  }
}
```

## Contributing to PESUAuth

Made with ❤️ by

[![Contributors](https://contrib.rocks/image?repo=pesu-dev/auth&nocache=1)](https://github.com/pesu-dev/auth/graphs/contributors)

*Powered by [contrib.rocks](https://contrib.rocks)*

If you'd like to contribute, please follow our [contribution guidelines](.github/CONTRIBUTING.md).
