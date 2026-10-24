# Metrics

How `/metrics` collects its counters, what each one means, and how to protect and scrape the endpoint. The request
parameters and responses are in the [README](../README.md#metrics).

## How collection works

Everything is counted **in this process, in memory**. There is no database and no external dependency, and the counters
**reset to zero when the process restarts**, which on the hosted environments is often. The process start time
(`startTimeSeconds` in JSON, `process_start_time_seconds` in Prometheus) is exposed so a dashboard can tell a restart
apart from a drop in traffic.

Collection happens at three layers, and which layer records what is deliberate:

| Layer                  | What it records                                                 | Why there                                                                                                                                                                                        |
| ---------------------- | --------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **HTTP middleware**    | request counts, status codes, matched route, latency, in-flight | It is the only place that sees every request, including ones that never reach a route                                                                                                            |
| **Exception handlers** | the error's exception class                                     | The middleware sees a status code; only the handler knows which class produced it. `UpstreamError` and `ProfileFetchError` are both `502`, and the class is the only thing that tells them apart |
| **`app/pesu.py`**      | upstream calls, client lifecycle, profile parsing               | These are not HTTP requests to this API at all, so nothing above could see them                                                                                                                  |

The middleware and the handlers write to **different metric families**, so a single failed request contributes exactly
one status sample and exactly one error sample, never two of either.

Two accounting rules hold at all times, and are the quickest way to tell whether the numbers are trustworthy:

```
requests.success + requests.failed + requestsInFlight  ==  requests.total
sum(responsesByStatus)                                 ==  requests.success + requests.failed
```

A login failure's *reason* comes from `errorsByType`, which names the exception class.
`authenticationResults` carries only the outcome, so the reason is recorded in exactly one place, and
`sum(authenticationResults) == authentication.total` modulo attempts still in flight.

`sum(errorsByType)` equals `requests.failed`, once no request is in flight: every failed response is rendered by an
exception handler of ours, so each is counted under its exception class. That includes a `404` for an unknown path
(`RouteNotFoundError`) and a `405` for an unsupported method (`MethodNotAllowedError`), which is where scanners
probing for other software show up.

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

## What each metric means

**Traffic**

| Metric                                | Meaning                                                                                                                                                                                                                                                                  |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `requests_total`                      | Requests received, counted on arrival                                                                                                                                                                                                                                    |
| `requests_success_total`              | Answered with a status below 400                                                                                                                                                                                                                                         |
| `requests_failed_total`               | Answered with a status of 400 or above                                                                                                                                                                                                                                   |
| `requests_in_flight`                  | Received but not yet answered. A gauge; it is what explains the gap in the totals                                                                                                                                                                                        |
| `responses_total{status}`             | Responses by HTTP status code                                                                                                                                                                                                                                            |
| `route_requests_total{method,route}`  | Requests by matched route template and method. Never a caller-supplied path: the docs pages and `/openapi.json` appear under their fixed paths, any other unmatched path becomes `<unmatched>` rather than a new series per probe, and an unknown verb becomes `<other>` |
| `request_latency_seconds`             | Time to response start, all routes                                                                                                                                                                                                                                       |
| `route_latency_seconds{method,route}` | The same, per route                                                                                                                                                                                                                                                      |

**Failures**

| Metric                           | Meaning                                                                                                                                                                                                                                                                                                         |
| -------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `failures_total{fault}`          | Failed requests by whose fault it was: `client` for 4xx, `server` for 5xx. Alert on `server` without enumerating status codes                                                                                                                                                                                   |
| `errors_total{type}`             | Errors rendered by an exception handler, by exception class: `AuthenticationError`, `UpstreamError`, `ProfileFetchError`, `ProfileParseError`, `MetricsAuthorizationError`, `RequestBodyParseError`, `RequestValidationError`, `RouteNotFoundError`, `MethodNotAllowedError`, or whatever reached the catch-all |
| `validation_errors_total{field}` | Request validation failures by the field that failed. Unrecognised keys collapse into `other`, since the request body is caller-controlled                                                                                                                                                                      |

**Authentication**

| Metric                                   | Meaning                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| ---------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `authentication_requests_total{profile}` | Authentication requests, split by whether profile data was asked for                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| `authentication_results_total{result}`   | Attempts by outcome: `success` or `failure`. Deliberately only those two; `errors_total` already names the exception class, and recording the reason here too would put one fact in two places. This family exists for the login **success rate**, where success and failure share a denominator                                                                                                                                                                                                                                                                                                                                                                                        |
| `profile_field_filtering_total{enabled}` | Profile fetches, split by whether the caller narrowed the returned fields. Recorded where the branch is taken, so a caller passing exactly the default list, in any order, counts as `false`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| `profile_parse_errors_total{reason}`     | Profile response problems by what broke: `response_structure` (the response could not be parsed, a `422`), `unknown_campus_code` (a campus name with no known campus code), `missing_field` (a field PESU Academy did not send at all) and `unexpected_value` (a field sent in an unexpected shape). The last two are counted once per field, returned to the caller as `null`, and named in the log. `response_structure`, `missing_field` and `unexpected_value` mean PESU Academy's API changed; `unknown_campus_code` usually means a new campus, or a new way of writing a campus's name. A field PESU Academy sends with no value is not counted: that is a student with no value |

**Upstream (PESU Academy)**

PESU Academy is the only dependency this service has, and the only thing that can be slow or down. Its latency is
measured separately from the API's own, so a slow request can be attributed rather than guessed at. Two operations,
both calls to PESU Academy: `login`, and `profile_fetch` (made only when a profile is requested).

| Metric                                       | Meaning                                                                                                                                                             |
| -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `upstream_requests_total{operation,outcome}` | Calls by outcome: `success`, `error` (raised, including timeouts), `cancelled` (we walked away: a disconnect or a shutdown, deliberately *not* counted as an error) |
| `upstream_responses_total{operation,status}` | The status code PESU Academy returned                                                                                                                               |
| `upstream_latency_seconds{operation}`        | Seconds spent waiting on each operation                                                                                                                             |

A wrong password counts as a **successful** `login` call: PESU answered, with a `401`. The call worked; the
credentials did not. Likewise a profile response we cannot parse is a successful `profile_fetch`; the fetch worked and
our parsing of it did not.

**Internals**

| Metric                         | Meaning                                                                                                                                                                                                     |
| ------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `http_clients_total{event}`    | `created`, `closed`, `close_failed`. **`created` minus `closed` is how many are still open**, which should be `0` at rest; each login closes its own client. A number that climbs is a connection-pool leak |
| `lifespan_events_total{event}` | `startup` and `shutdown` seen by this process                                                                                                                                                               |
| `process_start_time_seconds`   | Start time since the Unix epoch. A gauge, so restarts are visible                                                                                                                                           |

## Prometheus response

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

## JSON response

The same numbers, with labels folded into object keys: `responsesByStatus` keyed by status code, `requestsByRoute` by
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

## Protecting the endpoint

`/metrics` is **open unless a token is configured**, through the `METRICS_TOKEN` environment
variable.

| `METRICS_TOKEN` | Behaviour of `/metrics`                                               |
| --------------- | --------------------------------------------------------------------- |
| unset           | Open. A credential sent anyway is **ignored, not rejected**           |
| blank           | Same as unset; an empty value means "no token", not "the empty token" |
| set             | Every request must carry that token, in both formats                  |

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

The API Explorer at `/` shows a **Bearer token** password field for operations marked with bearer
security in the OpenAPI specification. When `METRICS_TOKEN` is set, enter it before sending the
request. A nonempty token is sent in the `Authorization: Bearer <token>` header and included in
**Copy request**. It is never saved to browser storage and is cleared when switching endpoints.
Copied commands contain any credentials you entered; do not share them publicly. Swagger UI at
`/docs` also supports tokens through its **Authorize** button.

The variable is read once at startup, so changing it needs a restart. No other endpoint is
affected; `/health` in particular stays open, since uptime monitors and the hosting platform's own
health check send no credentials.

## Scraping the endpoint

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
