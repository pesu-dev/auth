# Testing

We use `pytest`, and a pre-commit hook ensures tests are run automatically before every commit.

To run tests manually:

```bash
uv run pytest
```

To check coverage:

```bash
uv run pytest --cov
```

Coverage is measured over every Python file outside `tests/` (`app/`, `scripts/` and
`.github/scripts/`), counting branches as well as lines, and the gate is **100%**. It is configured
once, under `[tool.coverage]` in `pyproject.toml`, so the command above, the pre-commit hook and CI
all enforce the same thing. Only the `if __name__ == "__main__":` line of a script is excluded; keep
its logic in a function that a test can call.

> [!NOTE]
> The pre-commit hook runs `python scripts/run_tests.py`, which uses the same underlying `pytest` runner.

## Tests that need credentials

The tests marked `secret_required` log in to PESU Academy for real. They need the
`TEST_*` variables in your `.env`. If any of `TEST_EMAIL`, `TEST_PRN`, `TEST_SRN`, `TEST_MOBILE` or `TEST_PASSWORD` is
missing, `scripts/run_tests.py` deselects those tests, warns that it has done so, and still enforces the coverage gate
on the rest.

The live tests all sign in to the same PESU Academy account. PESU Academy accepts more than one session for an
account at a time, so a run does not fail because another is in flight, but every run makes real logins to PESU
Academy: run them when you need them, not in a loop.

The live tests compare the profile PESU Academy returns with the `TEST_*` values field by field, so a
failure there after a PESU Academy release usually means their API changed rather than our code.
The tests that are not marked `secret_required` still call PESU Academy (with invalid credentials), so
only `tests/unit/` runs offline.

In CI, pull requests come from forks, and GitHub withholds secrets from fork pull requests. So
the *Test suite & coverage* job of the *CI Checks* workflow runs the reduced suite on every pull request -- it says so in the run's summary
-- and the live tests only run once the change reaches `dev`. Run them locally before you open a
pull request; CI will not cover them for you.

## Benchmarks

The scripts in `scripts/benchmark/` write their CSVs and plots to `benchmark/results/` at the
repository root, named `{script}_{date}_{time}.{ext}`, or `{script}_{date}_{time}_{tag}.{ext}` with `--tag`, which
labels an experimental run. Pass `--output-dir` to write elsewhere, or `--output` to name one file explicitly. All of it is
gitignored.

Each row of `benchmark_requests.py`'s CSV is one request: `status` (1 for a success), `time` (its latency in seconds)
and `start` (when it started, in seconds from the start of the run). Throughput comes from elapsed time, never from the
sum of the latencies, which overlap in a `--parallel` run: `benchmark_requests.py` times the whole run, and
`analyze_benchmark.py` measures from the first request's start to the last one's end. It still reads an older CSV
without `start`, and says when it has had to fall back to adding the latencies up, which is only right for a
sequential run.

```bash
cd scripts/benchmark
uv run --group benchmark python benchmark_requests.py --num-requests 100 --parallel --tag baseline
uv run --group benchmark python analyze_benchmark.py -f ../../benchmark/results/benchmark_requests_*.csv
```

`benchmark_requests.py` signs in with `TEST_PRN` and `TEST_PASSWORD` from your `.env`, so every request
is a real login to PESU Academy through the API you point it at. Keep `--num-requests` small, and do not
run it alongside the live tests: both wait on PESU Academy, so each skews the other's timings.

## Writing tests

- Write tests for all new features and bug fixes
- Place them in the `tests/` directory
- Name your test files and functions with the `test_` prefix (required by `pytest` and validated by pre-commit)
- Keep test cases small, meaningful, and well-named
- Never let a unit test reach PESU Academy. `tests/unit/conftest.py` has fixtures for this:
  `upstream` replaces the client's `post()`, and `wire` serves responses at the transport layer so a
  test can inspect the exact requests sent, through the whole app if needed
  (`tests/unit/test_authenticate_flow.py`)
- Put assertions about an exception after its `with pytest.raises(...)` block, not inside it, where
  they never run
- Adding a profile field? See [Adding a profile field](development.md#adding-a-profile-field)
