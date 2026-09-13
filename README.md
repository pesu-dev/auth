# pesu-auth

[![Docker Image Build](https://github.com/pesu-dev/auth/actions/workflows/docker.yaml/badge.svg)](https://github.com/pesu-dev/auth/actions/workflows/docker.yml)
[![Pre-Commit Checks](https://github.com/pesu-dev/auth/actions/workflows/pre-commit.yaml/badge.svg)](https://github.com/pesu-dev/auth/actions/workflows/pre-commit.yaml)
[![Lint](https://github.com/pesu-dev/auth/actions/workflows/lint.yaml/badge.svg)](https://github.com/pesu-dev/auth/actions/workflows/lint.yaml)
[![Deploy](https://github.com/pesu-dev/auth/actions/workflows/deploy-prod.yaml/badge.svg)](https://github.com/pesu-dev/auth/actions/workflows/deploy-prod.yaml)

[![Docker Automated build](https://img.shields.io/docker/automated/pesudev/pesu-auth?logo=docker)](https://hub.docker.com/r/pesudev/pesu-auth/builds)
[![Docker Image Version (tag)](https://img.shields.io/docker/v/pesudev/pesu-auth/latest?logo=docker&label=build%20commit)](https://hub.docker.com/r/pesudev/pesu-auth/tags)
[![Docker Image Size (tag)](https://img.shields.io/docker/image-size/pesudev/pesu-auth/latest?logo=docker)](https://hub.docker.com/r/pesudev/pesu-auth)

A simple and lightweight API to authenticate PESU credentials using PESU Academy.

The API is secure and protects user privacy by not storing any user credentials. It only validates credentials and
returns the user's profile information. No personal data is stored.

## PESUAuth LIVE Deployment

- You can access the PESUAuth API endpoints [here](https://pesu-auth.onrender.com/).
- You can view the health status of the API on the [PESUAuth Health Dashboard](https://xzlk85cp.status.cron-job.org/).

#### API Status

![Cron job status](https://api.cron-job.org/jobs/4424640/69701a6f8df1d307/status-7.svg)\
![Cron job status](https://api.cron-job.org/jobs/6338038/9feb0f217be714ec/status-7.svg)\
![Cron job status](https://api.cron-job.org/jobs/5672615/1d744f1dc18fb505/status-7.svg)\
![Cron job status](https://api.cron-job.org/jobs/4424663/d5a30351867acec9/status-7.svg)

> [!NOTE]
> All timestamps are in UTC.

> [!WARNING]
> The live version is hosted on a free tier server located in the United States. As a result, you *might* experience higher latencies and slower response times, compared to running the API locally or on a server closer to your location.

## How to run PESUAuth locally

Running the PESUAuth API locally is simple. Clone the repository and follow the steps below to get started.

> [!TIP]
> We recommend running the API locally using Docker for ease of use, the best performance, and lowest latency.

### Running with Docker

This is the easiest and recommended way to run the API locally. Ensure you have Docker installed on your system. Run the
following commands to start the API.

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

| **Parameter** | **Optional** | **Type**    | **Default** | **Description**                                                                                 |
| ------------- | ------------ | ----------- | ----------- | ----------------------------------------------------------------------------------------------- |
| `username`    | No           | `str`       |             | The user's SRN or PRN                                                                           |
| `password`    | No           | `str`       |             | The user's password                                                                             |
| `profile`     | Yes          | `boolean`   | `False`     | Whether to fetch profile information                                                            |
| `fields`      | Yes          | `list[str]` | `None`      | Which fields to fetch from the profile information. If not provided, all fields will be fetched |

#### Response Object

On authentication, it returns the following parameters in a JSON object. If the authentication was successful and
profile data was requested, the response's `profile` key will store a dictionary with a user's profile information.
**On an unsuccessful sign-in, this field will not exist**.

| **Field**   | **Type**        | **Description**                                                          |
| ----------- | --------------- | ------------------------------------------------------------------------ |
| `status`    | `boolean`       | A flag indicating whether the overall request was successful             |
| `profile`   | `ProfileObject` | A nested map storing the profile information, returned only if requested |
| `message`   | `str`           | A message that provides information corresponding to the status          |
| `timestamp` | `datetime`      | A timezone offset timestamp indicating the time of authentication        |

##### `ProfileObject`

This object contains the user's profile information, which is returned only if the `profile` parameter is set to `True`.
If the authentication fails, this field will not be present in the response.

| **Field**    | **Description**                                        |
| ------------ | ------------------------------------------------------ |
| `name`       | Name of the user                                       |
| `prn`        | PRN of the user                                        |
| `srn`        | SRN of the user                                        |
| `program`    | Academic program that the user is enrolled into        |
| `branch`     | Complete name of the branch that the user is pursuing  |
| `semester`   | Current semester that the user is in                   |
| `section`    | Section of the user                                    |
| `email`      | Email address of the user registered with PESU         |
| `phone`      | Phone number of the user registered with PESU          |
| `campusCode` | The integer code of the campus (1 for RR and 2 for EC) |
| `campus`     | Abbreviation of the user's campus name                 |

### `/health`

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

#### How collection works

Everything is counted **in this process, in memory**. There is no database and no external dependency, and the counters
**reset to zero when the process restarts** — which on the hosted environments is often. `processStartTimeSeconds` is
exposed so a dashboard can tell a restart apart from a drop in traffic.

Collection happens at three layers, and which layer records what is deliberate:

| Layer                  | What it records                                                               | Why there                                                                                                                                                                                         |
| ---------------------- | ----------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **HTTP middleware**    | request counts, status codes, matched route, latency, in-flight               | It is the only place that sees every request, including ones that never reach a route                                                                                                             |
| **Exception handlers** | the error's exception class                                                   | The middleware sees a status code; only the handler knows which class produced it. `CSRFTokenError` and `ProfileFetchError` are both `502`, and the class is the only thing that tells them apart |
| **`app/pesu.py`**      | upstream calls, CSRF cache, prefetch tasks, client lifecycle, profile parsing | These are not HTTP requests to this API at all, so nothing above could see them                                                                                                                   |

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

| Metric                           | Meaning                                                                                                                                                                                                     |
| -------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `failures_total{fault}`          | Failed requests by whose fault it was: `client` for 4xx, `server` for 5xx. Alert on `server` without enumerating status codes                                                                               |
| `errors_total{type}`             | Errors rendered by an exception handler, by exception class: `AuthenticationError`, `CSRFTokenError`, `ProfileFetchError`, `ProfileParseError`, `RequestValidationError`, or whatever reached the catch-all |
| `validation_errors_total{field}` | Request validation failures by the field that failed. Unrecognised keys collapse into `other`, since the request body is caller-controlled                                                                  |

**Authentication**

| Metric                                   | Meaning                                                                                                                                                                                                                                                                                           |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `authentication_requests_total{profile}` | Authentication requests, split by whether profile data was asked for                                                                                                                                                                                                                              |
| `authentication_results_total{result}`   | Attempts by outcome: `success` or `failure`. Deliberately only those two — `errors_total` already names the exception class, and recording the reason here too would put one fact in two places. This family exists for the login **success rate**, where success and failure share a denominator |
| `profile_field_filtering_total{enabled}` | Profile fetches, split by whether the caller narrowed the returned fields. Recorded where the branch is taken, so a caller passing exactly the default list counts as `false`                                                                                                                     |
| `profile_parse_errors_total{reason}`     | Parse failures by what broke: `key_missing`, `value_missing`, `unknown_field`, `page_structure`, `no_data`, `unknown_campus_code`. These mean PESU Academy's page changed                                                                                                                         |

**Upstream (PESU Academy)**

PESU Academy is the only dependency this service has, and the only thing that can be slow or down. Its latency is
measured separately from the API's own, so a slow request can be attributed rather than guessed at. Three operations:
`csrf_fetch` (the pre-login token), `login`, and `profile_fetch`.

| Metric                                       | Meaning                                                                                                                                                              |
| -------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `upstream_requests_total{operation,outcome}` | Calls by outcome: `success`, `error` (raised, including timeouts), `cancelled` (we walked away — a disconnect or a shutdown, deliberately *not* counted as an error) |
| `upstream_responses_total{operation,status}` | The status code PESU Academy returned                                                                                                                                |
| `upstream_latency_seconds{operation}`        | Seconds spent waiting on each operation                                                                                                                              |

A wrong password counts as a **successful** `login` call: PESU answered with a `200` and a login form. The call worked;
the credentials did not. Likewise a missing CSRF tag is a successful `csrf_fetch` — the fetch worked and our parsing of
it did not.

**Internals**

| Metric                          | Meaning                                                                                                                                                                                           |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `csrf_cache_total{outcome}`     | `hit` or `miss` on the prefetched CSRF client. A miss means a caller waited on the upstream round trip the prefetch exists to avoid, so the hit rate is how well the prefetch is working          |
| `csrf_refreshes_total{outcome}` | The periodic background token refresh, by outcome                                                                                                                                                 |
| `prefetch_tasks_total{outcome}` | Background prefetch tasks: `success`, `failure`, `cancelled`. A failure is not fatal — the cache stays empty and the next request fetches inline                                                  |
| `http_clients_total{event}`     | `created`, `closed`, `close_failed`. **`created` minus `closed` is how many are still open**, which should be `1` at rest — the prefetched client. A number that climbs is a connection-pool leak |
| `lifespan_events_total{event}`  | `startup` and `shutdown` seen by this process                                                                                                                                                     |
| `process_start_time_seconds`    | Start time since the Unix epoch. A gauge, so restarts are visible                                                                                                                                 |

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
pesu_auth_requests_failed_total 182
# HELP pesu_auth_responses_total HTTP responses, by status code.
# TYPE pesu_auth_responses_total counter
pesu_auth_responses_total{status="200"} 1094
pesu_auth_responses_total{status="308"} 8
pesu_auth_responses_total{status="400"} 12
pesu_auth_responses_total{status="401"} 160
pesu_auth_responses_total{status="500"} 4
pesu_auth_responses_total{status="502"} 6
# HELP pesu_auth_route_requests_total HTTP requests, by matched route and method.
# TYPE pesu_auth_route_requests_total counter
pesu_auth_route_requests_total{method="GET",route="/health"} 302
pesu_auth_route_requests_total{method="POST",route="/authenticate"} 774
# HELP pesu_auth_errors_total Errors rendered by an exception handler, by exception class.
# TYPE pesu_auth_errors_total counter
pesu_auth_errors_total{type="AuthenticationError"} 160
pesu_auth_errors_total{type="ProfileFetchError"} 2
pesu_auth_errors_total{type="RequestValidationError"} 12
# HELP pesu_auth_authentication_requests_total Authentication requests, by whether profile data was requested.
# TYPE pesu_auth_authentication_requests_total counter
pesu_auth_authentication_requests_total{profile="false"} 640
pesu_auth_authentication_requests_total{profile="true"} 134
# HELP pesu_auth_authentication_results_total Authentication attempts, by outcome. errors_total says why one failed.
# TYPE pesu_auth_authentication_results_total counter
pesu_auth_authentication_results_total{result="failure"} 162
pesu_auth_authentication_results_total{result="success"} 612
# HELP pesu_auth_profile_field_filtering_total Profile fetches, by whether the caller narrowed the fields returned.
# TYPE pesu_auth_profile_field_filtering_total counter
pesu_auth_profile_field_filtering_total{enabled="false"} 94
pesu_auth_profile_field_filtering_total{enabled="true"} 40
# HELP pesu_auth_profile_parse_errors_total Profile page parse failures, by what could not be parsed.
# TYPE pesu_auth_profile_parse_errors_total counter
pesu_auth_profile_parse_errors_total{reason="unknown_field"} 3
# HELP pesu_auth_validation_errors_total Request validation failures, by the field that failed.
# TYPE pesu_auth_validation_errors_total counter
pesu_auth_validation_errors_total{field="password"} 4
pesu_auth_validation_errors_total{field="username"} 8
# HELP pesu_auth_failures_total Failed requests, by whose fault it was: the caller's (4xx) or ours (5xx).
# TYPE pesu_auth_failures_total counter
pesu_auth_failures_total{fault="client"} 172
pesu_auth_failures_total{fault="server"} 10
# HELP pesu_auth_request_latency_seconds Seconds from receiving a request to starting its response.
# TYPE pesu_auth_request_latency_seconds summary
pesu_auth_request_latency_seconds_sum 742.1841932
pesu_auth_request_latency_seconds_count 1284
# HELP pesu_auth_route_latency_seconds Seconds from receiving a request to starting its response, by route.
# TYPE pesu_auth_route_latency_seconds summary
pesu_auth_route_latency_seconds_sum{method="GET",route="/health"} 0.413
pesu_auth_route_latency_seconds_sum{method="POST",route="/authenticate"} 741.2118
pesu_auth_route_latency_seconds_count{method="GET",route="/health"} 302
pesu_auth_route_latency_seconds_count{method="POST",route="/authenticate"} 774
# HELP pesu_auth_upstream_requests_total Requests made to PESU Academy, by operation and outcome.
# TYPE pesu_auth_upstream_requests_total counter
pesu_auth_upstream_requests_total{operation="csrf_fetch",outcome="error"} 3
pesu_auth_upstream_requests_total{operation="csrf_fetch",outcome="success"} 790
pesu_auth_upstream_requests_total{operation="login",outcome="cancelled"} 1
pesu_auth_upstream_requests_total{operation="login",outcome="error"} 2
pesu_auth_upstream_requests_total{operation="login",outcome="success"} 774
pesu_auth_upstream_requests_total{operation="profile_fetch",outcome="error"} 1
pesu_auth_upstream_requests_total{operation="profile_fetch",outcome="success"} 134
# HELP pesu_auth_upstream_responses_total Responses from PESU Academy, by operation and status code.
# TYPE pesu_auth_upstream_responses_total counter
pesu_auth_upstream_responses_total{operation="csrf_fetch",status="200"} 790
pesu_auth_upstream_responses_total{operation="login",status="200"} 774
pesu_auth_upstream_responses_total{operation="profile_fetch",status="200"} 134
# HELP pesu_auth_upstream_latency_seconds Seconds spent waiting on PESU Academy, by operation.
# TYPE pesu_auth_upstream_latency_seconds summary
pesu_auth_upstream_latency_seconds_sum{operation="csrf_fetch"} 210.4
pesu_auth_upstream_latency_seconds_sum{operation="login"} 620.4
pesu_auth_upstream_latency_seconds_sum{operation="profile_fetch"} 190.2
pesu_auth_upstream_latency_seconds_count{operation="csrf_fetch"} 793
pesu_auth_upstream_latency_seconds_count{operation="login"} 776
pesu_auth_upstream_latency_seconds_count{operation="profile_fetch"} 135
# HELP pesu_auth_csrf_cache_total Lookups of the cached unauthenticated CSRF client, by whether the cache was warm.
# TYPE pesu_auth_csrf_cache_total counter
pesu_auth_csrf_cache_total{outcome="hit"} 760
pesu_auth_csrf_cache_total{outcome="miss"} 14
# HELP pesu_auth_csrf_refreshes_total Periodic background refreshes of the unauthenticated CSRF token, by outcome.
# TYPE pesu_auth_csrf_refreshes_total counter
pesu_auth_csrf_refreshes_total{outcome="failure"} 1
pesu_auth_csrf_refreshes_total{outcome="success"} 45
# HELP pesu_auth_prefetch_tasks_total Background CSRF prefetch tasks, by outcome.
# TYPE pesu_auth_prefetch_tasks_total counter
pesu_auth_prefetch_tasks_total{outcome="failure"} 4
pesu_auth_prefetch_tasks_total{outcome="success"} 770
# HELP pesu_auth_http_clients_total Upstream HTTP client lifecycle. created minus closed is how many are still open.
# TYPE pesu_auth_http_clients_total counter
pesu_auth_http_clients_total{event="closed"} 775
pesu_auth_http_clients_total{event="created"} 776
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
  "uptimeSeconds": 0.0,
  "requests": {
    "total": 1284,
    "success": 1102,
    "failed": 182
  },
  "latency": {
    "sumSeconds": 742.1841932,
    "count": 1284,
    "averageSeconds": 0.5780250725856698
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
    "502": 6
  },
  "requestsByRoute": {
    "GET /health": {
      "requests": 302,
      "latency": {
        "sumSeconds": 0.413,
        "count": 302,
        "averageSeconds": 0.0013675496688741722
      }
    },
    "POST /authenticate": {
      "requests": 774,
      "latency": {
        "sumSeconds": 741.2118,
        "count": 774,
        "averageSeconds": 0.957637984496124
      }
    }
  },
  "errorsByType": {
    "AuthenticationError": 160,
    "ProfileFetchError": 2,
    "RequestValidationError": 12
  },
  "requestsInFlight": 1,
  "failuresByFault": {
    "client": 172,
    "server": 10
  },
  "validationErrorsByField": {
    "password": 4,
    "username": 8
  },
  "authenticationResults": {
    "failure": 162,
    "success": 612
  },
  "profileFieldFiltering": {
    "false": 94,
    "true": 40
  },
  "profileParseErrors": {
    "unknown_field": 3
  },
  "upstream": {
    "csrf_fetch": {
      "success": 790,
      "error": 3,
      "cancelled": 0,
      "latency": {
        "sumSeconds": 210.4,
        "count": 793,
        "averageSeconds": 0.26532156368221943
      },
      "responsesByStatus": {
        "200": 790
      }
    },
    "login": {
      "success": 774,
      "error": 2,
      "cancelled": 1,
      "latency": {
        "sumSeconds": 620.4,
        "count": 776,
        "averageSeconds": 0.7994845360824742
      },
      "responsesByStatus": {
        "200": 774
      }
    },
    "profile_fetch": {
      "success": 134,
      "error": 1,
      "cancelled": 0,
      "latency": {
        "sumSeconds": 190.2,
        "count": 135,
        "averageSeconds": 1.4088888888888889
      },
      "responsesByStatus": {
        "200": 134
      }
    }
  },
  "csrfCache": {
    "hit": 760,
    "miss": 14
  },
  "csrfRefreshes": {
    "failure": 1,
    "success": 45
  },
  "prefetchTasks": {
    "failure": 4,
    "success": 770
  },
  "httpClients": {
    "closed": 775,
    "created": 776
  },
  "lifespanEvents": {
    "startup": 1
  }
}
```

</details>

#### Protecting the endpoint

`/metrics` is **open by default**, which is what a local run and the Docker instructions above
expect. Set the `METRICS_TOKEN` environment variable on the server to require a bearer token
instead:

```bash
TOKEN=$(openssl rand -hex 32)   # keep it: whatever scrapes the endpoint needs the same value
docker run --name pesu-auth -d -p 5000:5000 -e METRICS_TOKEN="$TOKEN" pesu-auth
```

With it set, a request must carry that token or the endpoint answers `401` with
`WWW-Authenticate: Bearer` and the same error body as every other failure. Both formats are
covered, so `?fmt=json` is not a way around it.

```bash
curl http://localhost:5000/metrics                                   # 401
curl -H "Authorization: Bearer <token>" http://localhost:5000/metrics  # 200
```

The variable is read once at startup, so changing it needs a restart. Leaving it blank counts as
unset. No other endpoint is affected — `/health` in particular stays open, since uptime monitors
and the hosting platform's own health check send no credentials.

#### Scraping the endpoint

The default format is the Prometheus text exposition format precisely so that a scraper pointed at
this path needs no configuration. Any Prometheus-compatible collector works:

```yaml
scrape_configs:
  - job_name: pesu-auth
    metrics_path: /metrics
    scheme: https
    static_configs:
      - targets: [ "pesu-auth.onrender.com" ]
    authorization:
      credentials: <token>   # omit when METRICS_TOKEN is unset
```

### `/readme`

This endpoint redirects to the project's official GitHub repository. This endpoint does not take any request parameters.

### Integrating your application with the PESUAuth API

Here are some examples of how you can integrate your application with the PESUAuth API using Python and cURL.

#### Python

##### Request

```python
import requests

data = {
    "username": "your SRN or PRN here",
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
    "name": "Johnny Blaze",
    "prn": "PES1201800001",
    "srn": "PES1201800001",
    "program": "Bachelor of Technology",
    "branch": "Computer Science and Engineering",
    "semester": "NA",
    "section": "NA",
    "email": "johnnyblaze@gmail.com",
    "phone": "1234567890",
    "campusCode": 1,
    "campus": "RR"
  },
  "message": "Login successful.",
  "timestamp": "2024-07-28 22:30:10.103368+05:30"
}
```

#### cURL

##### Request

```bash
curl -X POST http://localhost:5000/authenticate \
-H "Content-Type: application/json" \
-d '{
    "username": "your SRN or PRN here",
    "password": "your password here"
}'
```

#### Response

```json
{
  "status": true,
  "message": "Login successful.",
  "timestamp": "2024-07-28 22:30:10.103368+05:30"
}
```

## Contributing to PESUAuth

Made with ❤️ by

[![Contributors](https://contrib.rocks/image?repo=pesu-dev/auth&nocache=1)](https://github.com/pesu-dev/auth/graphs/contributors)

*Powered by [contrib.rocks](https://contrib.rocks)*

If you'd like to contribute, please follow our [contribution guidelines](.github/CONTRIBUTING.md).
