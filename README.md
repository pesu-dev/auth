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

PESUAuth checks the username and password with [PESU Academy](https://www.pesuacademy.com/), through the same API
that the PESU Academy mobile app uses. If PESU Academy accepts them, the request succeeds; if it rejects them,
PESUAuth answers `401`. If you ask for the profile, PESUAuth fetches it too and returns it as a
[`ProfileObject`](#profileobject).

Credentials are only ever sent to PESU Academy, over HTTPS, and are never stored or logged. Nothing from one user's
sign-in is shared with another's.

> [!NOTE]
> PESU Academy's mobile API is not publicly documented and can change without notice. If it does, `/authenticate`
> may answer `422` or `502`, or return `null` for the profile fields that changed, until PESUAuth is updated to match.

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

1. Install the dependencies.

   ```bash
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

| **Endpoint**    | **Method**    | **Description**                                        |
| --------------- | ------------- | ------------------------------------------------------ |
| `/`             | `GET`, `HEAD` | Serves the interactive API Explorer.                   |
| `/docs`         | `GET`, `HEAD` | Serves the standard Swagger UI documentation.          |
| `/redoc`        | `GET`, `HEAD` | Serves the ReDoc API documentation.                    |
| `/openapi.json` | `GET`, `HEAD` | Serves the OpenAPI specification used by both UIs.     |
| `/authenticate` | `POST`        | Authenticates a user using their PESU credentials.     |
| `/health`       | `GET`, `HEAD` | A health check endpoint to monitor the API's status.   |
| `/metrics`      | `GET`, `HEAD` | Exposes traffic and error counters. See `fmt` below.   |
| `/readme`       | `GET`, `HEAD` | Redirects to the project's official GitHub repository. |

The Explorer builds request controls and response examples from `/openapi.json`. Enter the
required credentials, choose whether to fetch a profile, and optionally select profile fields.
Unselected fields are omitted, so requesting a profile with no fields selected returns the full
profile. **Copy request** copies a curl command for the current inputs; **Send request** calls the
API. The response's **Copy** button copies only the body, without its status or timing.

### Response headers

Every response includes the following baseline security headers:

- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: no-referrer`
- `X-Frame-Options: DENY`

Responses to `/authenticate` also include:

- `Cache-Control: no-store`

### `/authenticate`

You can send a request to the `/authenticate` endpoint with the user's credentials and the API will return a JSON
object, with the user's profile information if requested.

#### Request Parameters

| **Parameter** | **Optional** | **Type**    | **Default** | **Description**                                                                                                                                                                                                                                                                                            |
| ------------- | ------------ | ----------- | ----------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `username`    | No           | `str`       |             | The user's SRN, PRN, email address, or phone number. Maximum length is **96 characters**.                                                                                                                                                                                                                  |
| `password`    | No           | `str`       |             | The user's password, up to **128 characters**, counted exactly as typed. It is sent only to PESU Academy, and never stored or logged.                                                                                                                                                                      |
| `profile`     | Yes          | `boolean`   | `False`     | Whether to fetch profile information. This makes a second call to PESU Academy, so it takes longer                                                                                                                                                                                                         |
| `fields`      | Yes          | `list[str]` | `None`      | Which [`ProfileObject`](#profileobject) fields to return. A list can only be given when `profile` is `true`; otherwise the request is a `400`. If not provided or `null`, all fields are returned. Repeated names are ignored. Fields come back in the table's order, whatever order they are asked for in |

The request body is validated strictly. A missing or empty `username` or `password`, one that is not valid text, a `username` with a
line break or another invisible character, a value of the wrong type (such as
the string `"true"` for `profile`), an unknown key, an empty `fields` list, `fields` without `profile: true`, or an unknown field name is rejected with a
`400`. So is a body that cannot be read at all, such as JSON that is not valid UTF-8, with the fixed message
`Could not parse request body.`

#### Responses

| **Code** | **When**                                                                                                                                   |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `200`    | The credentials are valid. `profile` is included if it was requested                                                                       |
| `400`    | The request body failed validation, as described above                                                                                     |
| `401`    | PESU Academy rejected the credentials: a wrong password, or a user that does not exist                                                     |
| `422`    | PESU Academy's profile response could not be parsed or held no profile, which means their API changed. Only when the profile was requested |
| `500`    | An unexpected failure, rendered by the catch-all handler                                                                                   |
| `502`    | PESU Academy could not be reached, timed out, or answered the login or profile request unexpectedly                                        |

Every error this API renders carries the same `{status, message, timestamp}` body, with `status` set to `false`. That
includes a `404` for an unknown path and a `405` for an unsupported method, whose `Allow` header lists the methods
the path is served for.

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

Only the fields in the table below can be requested; any other name in `fields` is a `400`. A requested field is never left out for having no value, and **any field can be `null`** when PESU Academy has no value for it, does not send it, or sends it in an
unexpected shape. PESU Academy marks a missing value with `null` or an empty string, and both become `null`; any other text, `"NA"` included, is returned as
PESU Academy stores it, with surrounding whitespace trimmed. Fields come back in the order of the table below.

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

Everything else in PESU Academy's profile information, such as the photo, blood group, addresses, parents' details and marks, is
discarded and never returned, and cannot be requested in `fields`.

### `/health`

Answers `200` whenever the process is serving; a `500` would come from the catch-all handler, as on any other endpoint.

This endpoint can be used to check the health of the API. It's useful for monitoring and uptime checks. This endpoint
does not take any request parameters. Like every `GET` endpoint, it also answers `HEAD`, with the same status and
headers and no body, for monitors that check that way.

#### Response Object

| **Field**   | **Type**   | **Description**                                                     |
| ----------- | ---------- | ------------------------------------------------------------------- |
| `status`    | `boolean`  | `true` if healthy, `false` if there was an error                    |
| `message`   | `str`      | "ok" if healthy, error message otherwise                            |
| `timestamp` | `datetime` | A timezone offset timestamp indicating the time of the health check |

### `/metrics`

This endpoint exposes counters describing the traffic this process has served and the work it did to serve it. The
counters are kept in memory and reset to zero when the process restarts. It takes no request parameters other than the
format selector below.

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

The endpoint is open unless the `METRICS_TOKEN` environment variable is set. When it is, every request must carry that
token as a bearer token:

```bash
METRICS_TOKEN=<token> uv run python -m app.app
curl -H "Authorization: Bearer <token>" http://localhost:5000/metrics
```

#### Responses

| **Code** | **When**                                                                                   |
| -------- | ------------------------------------------------------------------------------------------ |
| `200`    | The counters, in the format named by `fmt`                                                 |
| `400`    | `fmt` was something other than `prometheus` or `json`                                      |
| `401`    | A token is configured and the request did not carry it. Carries `WWW-Authenticate: Bearer` |
| `500`    | An unexpected failure, rendered by the catch-all handler like on any other endpoint        |

See [docs/metrics.md](docs/metrics.md) for how the counters are collected, what each metric means, full example
responses, and how to protect and scrape the endpoint.

### `/readme`

This endpoint redirects to the project's official GitHub repository with a `308`, and takes no request parameters. A `500` would come from the catch-all handler, as on any other endpoint.

### Integrating your application with the PESUAuth API

Here is a request for a user's full profile, and the response.

```bash
curl -X POST http://localhost:5000/authenticate \
-H "Content-Type: application/json" \
-d '{
    "username": "your SRN, PRN, email or phone number here",
    "password": "your password here",
    "profile": true
}'
```

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

## Contributing to PESUAuth

Made with ❤️ by

[![Contributors](https://contrib.rocks/image?repo=pesu-dev/auth&nocache=1)](https://github.com/pesu-dev/auth/graphs/contributors)

*Powered by [contrib.rocks](https://contrib.rocks)*

If you'd like to contribute, please follow our [contribution guidelines](.github/CONTRIBUTING.md). Development, testing
and deployment are documented in [`docs/`](docs).
