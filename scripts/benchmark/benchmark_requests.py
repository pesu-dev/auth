"""Script to benchmark the PESUAuth API."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

from tqdm.auto import tqdm
from util import make_request

if __name__ == "__main__":
    """Main function to benchmark the PESUAuth API.

    This script benchmarks the PESUAuth API by making requests to the specified endpoint.
    It can be run in parallel using threads or sequentially.
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
        help="The output file to save the benchmark results to",
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
    if parallel:
        print(
            f"Running benchmark with max {max_workers} workers and {num_requests} requests in parallel...",
        )
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(
                    make_request,
                    profile=profile,
                    host=host,
                    route=route,
                    timeout=timeout,
                )
                for _ in range(num_requests)
            ]
            for future in as_completed(futures):
                try:
                    response, elapsed = future.result()
                    times.append(elapsed)
                    if verbose:
                        print(f"Response: {response}")
                    if response.get("status"):
                        success.append(1)
                    else:
                        success.append(0)
                except Exception as e:
                    print(f"Request failed: {e}")
    else:
        print(f"Running benchmark with {num_requests} requests sequentially...")
        for _ in tqdm(range(num_requests), desc="Processing requests"):
            response, elapsed = make_request(
                profile=profile,
                host=host,
                route=route,
                timeout=timeout,
            )
            times.append(elapsed)
            if verbose:
                print(f"Response: {response}")
            if response.get("status"):
                success.append(1)
            else:
                success.append(0)

    outfile = (
        output
        if output
        else (
            f"benchmark_[num_requests={num_requests}]_[max_workers={max_workers}]_"
            f"[parallel={parallel}]_[route={route}]_[timeout={timeout}].csv"
        )
    )

    with open(
        outfile,
        "w",
    ) as f:
        f.write("status,time\n")
        f.writelines(f"{s},{t}\n" for s, t in zip(success, times, strict=False))

    print(f"Benchmark completed. Successful requests: {sum(success)} out of {len(success)}")
    print(f"Average time per request: {sum(times) / len(times):.2f} seconds")
    print(f"Total time taken: {sum(times):.2f} seconds")
