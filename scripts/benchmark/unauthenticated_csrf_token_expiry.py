import argparse
import time
import os
from tqdm.auto import tqdm
from util import make_request


def test_response(response: dict, no_profile: bool) -> bool:
    """
    Test the response from the authenticate endpoint.
    """
    if response.get("status"):
        if not no_profile:
            return response.get("profile").get("prn") == os.getenv("TEST_PRN")
        return True
    return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test unauthenticated CSRF token expiry.")
    parser.add_argument(
        "--host",
        type=str,
        default="http://localhost:5000",
        help="The host to make the request to (default: http://localhost:5000)",
    )
    parser.add_argument(
        "--no-profile",
        action="store_true",
        help="Run the authenticate endpoint benchmark without fetching profile information (default: fetch profile info)",
    )
    parser.add_argument(
        "--timeout", type=int, default=10, help="The timeout for the request (default: 10)"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=10,
        help="The base interval between requests (default: 10 minutes)",
    )
    parser.add_argument(
        "--start-delay",
        type=int,
        default=0,
        help="The delay before starting the benchmark (default: 0 minutes)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="unauthenticated_csrf_token_expiry.csv",
        help="The output file name (default: unauthenticated_csrf_token_expiry.csv)",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Print the response for each request"
    )
    args = parser.parse_args()

    request_count, success, times, waiting_times = 0, list(), list(), [args.start_delay * 60]

    for _ in tqdm(
        range(args.start_delay * 60),
        desc=f"Waiting {args.start_delay} minutes before starting the benchmark",
        leave=False,
        unit="s",
    ):
        time.sleep(1)

    while True:
        request_count += 1
        response, elapsed = make_request(
            host=args.host, timeout=args.timeout, profile=not args.no_profile, route="authenticate"
        )
        success.append(int(test_response(response, args.no_profile)))
        times.append(elapsed)
        if args.verbose:
            print(f"Response: {response}")

        if success[-1] == 0:
            break

        next_interval = args.interval * request_count * 60
        for _ in tqdm(
            range(next_interval),
            desc=f"Waiting {next_interval / 60} minutes before next request",
            leave=False,
            unit="s",
        ):
            time.sleep(1)
        waiting_times.append(next_interval)

    with open(args.output, "w") as f:
        f.write("status,time,waiting_time\n")
        for s, t, w in zip(success, times, waiting_times):
            f.write(f"{s},{t},{w}\n")
