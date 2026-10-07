"""Script to benchmark the PESUAuth API."""

import argparse
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from tqdm.auto import tqdm
from util import make_request, resolve_output_path


def main() -> None:
    """Run the benchmark from the command line."""
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
    args = parser.parse_args()

    max_workers = args.max_workers
    num_requests = args.num_requests
    profile = not args.no_profile
    parallel = args.parallel
    host = args.host
    route = args.route
    timeout = args.timeout
    verbose = args.verbose
    output = args.output

    success = []
    times = []
    # When each request started, in seconds from the start of the run. In a parallel run the requests
    # overlap, so their latencies add up to far more than the run took; throughput has to come from
    # when they started and finished instead.
    starts = []
    run_started = time.perf_counter()

    def timed_request() -> tuple[dict, float, float]:
        """Make one request, noting when it started.

        Returns:
            tuple[dict, float, float]: The response body, its latency, and when it started.
        """
        started = time.perf_counter() - run_started
        response, elapsed = make_request(profile=profile, host=host, route=route, timeout=timeout)
        return response, elapsed, started

    if parallel:
        print(
            f"Running benchmark with max {max_workers} workers and {num_requests} requests in parallel...",
        )
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(timed_request) for _ in range(num_requests)]
            for future in as_completed(futures):
                try:
                    response, elapsed, started = future.result()
                    times.append(elapsed)
                    starts.append(started)
                    if verbose:
                        print(f"Response: {response}")
                    success.append(1 if response.get("status") else 0)
                except Exception as e:
                    print(f"Request failed: {e}")
    else:
        print(f"Running benchmark with {num_requests} requests sequentially...")
        for _ in tqdm(range(num_requests), desc="Processing requests"):
            response, elapsed, started = timed_request()
            times.append(elapsed)
            starts.append(started)
            if verbose:
                print(f"Response: {response}")
            success.append(1 if response.get("status") else 0)
    elapsed_total = time.perf_counter() - run_started

    outfile = resolve_output_path(
        script_name="benchmark_requests",
        extension="csv",
        output=output,
        output_dir=args.output_dir,
        tag=args.tag,
    )

    with open(outfile, "w") as f:
        f.write("status,time,start\n")
        f.writelines(f"{s},{t},{st}\n" for s, t, st in zip(success, times, starts, strict=True))

    print(f"Results saved to: {outfile}")
    print(f"Benchmark completed. Successful requests: {sum(success)} out of {len(success)}")
    # Every request can fail in the parallel runner, which records no time for a failure
    if times:
        print(f"Average time per request: {sum(times) / len(times):.2f} seconds")
    print(f"Elapsed time: {elapsed_total:.2f} seconds")
    print(f"Throughput: {len(times) / elapsed_total:.2f} requests/second")


if __name__ == "__main__":
    main()
