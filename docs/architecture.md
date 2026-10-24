# Architecture

PESUAuth is a small, stateless FastAPI service. It has no database and keeps nothing between requests except in-memory
[metrics](metrics.md). PESU Academy is its only dependency.

## Layout

| Path              | What it holds                                                                     |
| ----------------- | --------------------------------------------------------------------------------- |
| `app/app.py`      | The FastAPI app: routes, middleware, exception handlers, the OpenAPI schema, CLI  |
| `app/pesu.py`     | `PESUAcademy`: the login and profile calls to PESU Academy, and building profiles |
| `app/models/`     | Request, response, profile and metrics models, and the upstream response models   |
| `app/exceptions/` | `PESUAcademyError` and its subclasses, one per failure the API reports            |
| `app/metrics/`    | The metrics collector, its middleware, the Prometheus renderer and token check    |
| `app/docs/`       | The OpenAPI request and response examples for each route                          |
| `app/templates/`  | `playground.html`, the API Explorer served at `/`                                 |
| `scripts/`        | The test runner, the coding agent generator and the benchmarks                    |
| `tests/`          | Unit, functional and integration tests (see [testing.md](testing.md))             |

## How a request is handled

A call to `/authenticate` goes through these steps:

1. The metrics middleware counts the request and starts timing it.
1. FastAPI validates the body against `RequestModel`. A body that fails is answered with a `400`.
1. The route calls `PESUAcademy.authenticate`, which opens a new HTTP client for this request only.
1. It logs in to PESU Academy with the username and password. A rejected login is a `401`.
1. If a profile was asked for, it fetches it with the access token from the login, reads the fields it needs, and
   drops any fields that were not asked for.
1. The client is closed, whether the request succeeded or not.
1. The route returns the result as a `ResponseModel`, and the security headers are added to the response.

Every failure is raised as an exception and turned into the same `{status, message, timestamp}` body by an exception
handler, so no route builds an error response itself.

## Errors

Each failure the API reports is a subclass of `PESUAcademyError`, which carries its status code and the fixed message
the caller sees. The specifics, such as the username or what PESU Academy answered, go in `detail`, which only the log
sees.

| Exception                   | Status | When                                                              |
| --------------------------- | ------ | ----------------------------------------------------------------- |
| `RequestValidationError`    | `400`  | The request body or query failed validation (raised by FastAPI)   |
| `RequestBodyParseError`     | `400`  | The body could not be read at all, such as JSON that is not UTF-8 |
| `AuthenticationError`       | `401`  | PESU Academy rejected the credentials                             |
| `MetricsAuthorizationError` | `401`  | `METRICS_TOKEN` is set and the request did not carry it           |
| `RouteNotFoundError`        | `404`  | No route serves the path                                          |
| `MethodNotAllowedError`     | `405`  | The path is not served for the method                             |
| `ProfileParseError`         | `422`  | The profile response could not be parsed, so PESU's API changed   |
| `UpstreamError`             | `502`  | The login failed: PESU Academy was unreachable or answered oddly  |
| `ProfileFetchError`         | `502`  | The profile fetch failed, or PESU Academy declined to serve it    |
| anything else               | `500`  | An unexpected failure, rendered by the catch-all handler          |

## Calls to PESU Academy

- **Two calls at most:** a login, and a profile fetch only when the profile is asked for.
- **One client per request:** each request gets its own HTTP client, so no session state can pass from one user's
  login to another's. It is closed on every path, including errors and cancelled requests.
- **A 10-second timeout** on each call. A timeout or a connection failure is a `502`.
- **Redirects are not followed:** PESU Academy answers these calls directly, so a redirect means something changed, and
  it is reported as a `502`.
- **Values are returned as PESU Academy sends them:** a field it leaves out or sends in an unexpected shape becomes
  `null`, and is counted in `profile_parse_errors_total`.

## Privacy

Passwords and the access token PESU Academy issues are never logged, stored or returned. Validation errors are logged
without the submitted values, because they can include the whole request body. The username and the returned profile
are logged at `INFO`, to trace requests.
