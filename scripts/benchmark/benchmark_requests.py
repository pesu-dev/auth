"""Script to benchmark the PESUAuth API."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

from tqdm.auto import tqdm
from util import make_request, resolve_output_path

if TYPE_CHECKING:
    from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    """Build the command line parser for the benchmark.

    Returns:
        argparse.ArgumentParser: The parser.
    """
    parser = argparse.ArgumentParser(description="Benchmark PESUAuth API.")
    parser.add_argument(
        "--max-workers",
        type=int,
        default=10,
        help="Maximum number of concurrent workers (default: 10)",
    )
    parser.add_argument(
        "--num-requests",
        type=int,
        default=10,
        help="Number of requests to use for the benchmark (default: 10)",
    )
    parser.add_argument(
        "--no-profile",
        action="store_true",
        help="Run the authenticate endpoint benchmark without fetching profile information "
        "(default: fetch profile info)",
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Run the benchmark in parallel using threads",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="http://localhost:5000",
        help="The host to make the request to (default: http://localhost:5000)",
    )
    parser.add_argument(
        "--route",
        type=str,
        choices=["authenticate", "health", "readme"],
        default="authenticate",
        help="The route to make the request to (default: authenticate)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="The timeout for the request (default: 10.0)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose output (default: False)",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="The output file to save the benchmark results to (default: an auto-named CSV)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        help="The directory to write results into (default: benchmark/results at the repository root)",
    )
    parser.add_argument(
        "--tag",
        type=str,
        help="An identifier appended to the generated filename, for telling runs apart",
    )
    return parser


def _record(response: dict, elapsed: float, success: list[int], times: list[float], verbose: bool) -> None:
    """Record one finished request.

    Args:
        response (dict): The response body.
        elapsed (float): The seconds the request took.
        success (list[int]): Where to append 1 for a successful request and 0 otherwise.
        times (list[float]): Where to append the elapsed time.
        verbose (bool): Whether to print the response.
    """
    times.append(elapsed)
    if verbose:
        print(f"Response: {response}")
    success.append(1 if response.get("status") else 0)


def run_benchmark(args: argparse.Namespace) -> tuple[list[int], list[float]]:
    """Send the requests, one after another or in parallel.

    Args:
        args (argparse.Namespace): The parsed command line arguments.

    Returns:
        tuple[list[int], list[float]]: Per request, 1 or 0 for success, and the elapsed seconds.
    """
    request_options = {
        "profile": not args.no_profile,
        "host": args.host,
        "route": args.route,
        "timeout": args.timeout,
    }
    success: list[int] = []
    times: list[float] = []
    if args.parallel:
        print(
            f"Running benchmark with max {args.max_workers} workers and {args.num_requests} requests in parallel...",
        )
        with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            futures = [executor.submit(make_request, **request_options) for _ in range(args.num_requests)]
            for future in as_completed(futures):
                try:
                    response, elapsed = future.result()
                except Exception as e:
                    print(f"Request failed: {e}")
                    continue
                _record(response, elapsed, success, times, args.verbose)
    else:
        print(f"Running benchmark with {args.num_requests} requests sequentially...")
        for _ in tqdm(range(args.num_requests), desc="Processing requests"):
            response, elapsed = make_request(**request_options)
            _record(response, elapsed, success, times, args.verbose)
    return success, times


def write_results(success: list[int], times: list[float], outfile: Path) -> None:
    """Write the results as CSV and print a short summary.

    Args:
        success (list[int]): Per request, 1 for success and 0 otherwise.
        times (list[float]): Per request, the elapsed seconds.
        outfile (Path): The CSV file to write.
    """
    with open(outfile, "w") as f:
        f.write("status,time\n")
        f.writelines(f"{s},{t}\n" for s, t in zip(success, times, strict=False))

    print(f"Results saved to: {outfile}")
    print(f"Benchmark completed. Successful requests: {sum(success)} out of {len(success)}")
    # Every request can fail in the parallel runner, which records no time for a failure
    if times:
        print(f"Average time per request: {sum(times) / len(times):.2f} seconds")
    print(f"Total time taken: {sum(times):.2f} seconds")


def main(argv: list[str] | None = None) -> None:
    """Run the benchmark from the command line.

    Args:
        argv (list[str] | None): The arguments, defaulting to the process's own.
    """
    args = build_parser().parse_args(argv)
    success, times = run_benchmark(args)
    outfile = resolve_output_path(
        script_name="benchmark_requests",
        extension="csv",
        output=args.output,
        output_dir=args.output_dir,
        tag=args.tag,
    )
    write_results(success, times, outfile)


if __name__ == "__main__":
    main()
