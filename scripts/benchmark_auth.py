import os
import time

import httpx
import argparse
import logging
from tqdm.auto import tqdm
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed

load_dotenv()


def make_request(profile: bool = True) -> tuple[dict, float]:
    """
    Make a request to the authentication endpoint and return the response and elapsed time.
    :param profile: Whether to fetch the profile information or not
    :return: Tuple of response JSON and elapsed time in seconds
    """
    data = {
        "username": os.getenv("TEST_PRN"),
        "password": os.getenv("TEST_PASSWORD"),
        "profile": profile,
    }
    data2 = {
        "username": "PES1201800303",
        "password": "fandomlover123",
        "profile": profile,
    }
    with httpx.Client(follow_redirects=True, timeout=httpx.Timeout(10.0)) as client:
        start_time = time.time()
        response = client.post(
            "http://localhost:5000/authenticate",
            json=data,
            follow_redirects=True,
        )

        # response = client.post(
        #     "http://localhost:5000/authenticate",
        #     json=data2,
        #     follow_redirects=True,
        # )

    elapsed_time = time.time() - start_time
    return response.json(), elapsed_time


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark the authentication endpoint.")
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
        help="Run the benchmark without fetching profile information (default: fetch profile info)",
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Run the benchmark in parallel using threads",
    )
    args = parser.parse_args()

    max_workers = args.max_workers
    num_requests = args.num_requests
    profile = not args.no_profile
    parallel = args.parallel

    success = []
    times = []
    if parallel:
        logging.info(
            f"Running benchmark with max {max_workers} workers and {num_requests} requests in parallel..."
        )
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(make_request, profile=profile) for _ in range(num_requests)]
            for future in as_completed(futures):
                try:
                    response, elapsed = future.result()
                    times.append(elapsed)
                    logging.debug(response)
                    if response.get("status"):
                        success.append(1)
                    else:
                        success.append(0)
                except Exception as e:
                    logging.error(f"Request failed: {e}")
    else:
        logging.info(f"Running benchmark with {num_requests} requests sequentially...")
        for _ in tqdm(range(num_requests), desc="Processing requests"):
            response, elapsed = make_request(profile=profile)
            times.append(elapsed)
            logging.debug(response)
            if response.get("status"):
                success.append(1)
            else:
                success.append(0)

    with open(
        f"benchmark_[num_requests={num_requests}]_[max_workers={max_workers}]_[parallel={parallel}].csv",
        "w",
    ) as f:
        f.write("status,time\n")
        for s, t in zip(success, times):
            f.write(f"{s},{t}\n")

    print(f"Benchmark completed. Successful requests: {sum(success)} out of {len(success)}")
    print(f"Average time per request: {sum(times) / len(times):.2f} seconds")
    print(f"Total time taken: {sum(times):.2f} seconds")
