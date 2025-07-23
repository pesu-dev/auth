import asyncio
import logging
import time
import os
from datetime import datetime
from typing import Optional
import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("auth_monitor.log"), logging.StreamHandler()],
)


class AuthMonitor:
    """
    Monitors authentication by sending requests at increasing intervals.
    """

    def __init__(self, base_interval_minutes: int = 1, max_iterations: int | None = None):
        self.base_interval = base_interval_minutes * 60  # Convert to seconds
        self.max_iterations = max_iterations
        self.iteration = 0
        self.username = os.getenv("TEST_PRN")
        self.password = os.getenv("TEST_PASSWORD")
        self.endpoint = os.getenv("AUTH_ENDPOINT", "http://localhost:5000/authenticate")

        if not self.username or not self.password:
            raise ValueError("TEST_PRN and TEST_PASSWORD must be set in environment variables")

    async def send_auth_request(self) -> dict:
        """Send authentication request to the endpoint."""
        data = {"username": self.username, "password": self.password, "profile": True}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                start_time = time.time()
                response = await client.post(self.endpoint, json=data)
                elapsed_time = time.time() - start_time

                result = {
                    "status_code": response.status_code,
                    "response": response.json() if response.status_code == 200 else response.text,
                    "elapsed_time": elapsed_time,
                    "timestamp": datetime.now().isoformat(),
                }

                logging.info(
                    f"Request completed in {elapsed_time:.3f}s - Status: {response.status_code}"
                )
                return result

        except Exception as e:
            error_result = {"error": str(e), "timestamp": datetime.now().isoformat()}
            logging.error(f"Request failed: {e}")
            return error_result

    def calculate_wait_time(self) -> int:
        """Calculate wait time based on current iteration."""
        return self.base_interval * (self.iteration + 1)

    async def run_monitor(self):
        """Run the monitoring loop with increasing intervals."""
        logging.info(
            f"Starting auth monitor with base interval: {self.base_interval // 60} minutes"
        )
        logging.info(f"Endpoint: {self.endpoint}")
        logging.info(f"Username: {self.username}")

        # Send initial request immediately
        logging.info(f"=== Iteration {self.iteration + 1} ===")
        result = await self.send_auth_request()
        logging.info(f"Result: {result}")

        self.iteration += 1

        # Continue with scheduled requests
        while self.max_iterations is None or self.iteration < self.max_iterations:
            wait_time = self.calculate_wait_time()
            wait_minutes = wait_time // 60

            logging.info(f"Waiting {wait_minutes} minutes until next request...")
            await asyncio.sleep(wait_time)

            logging.info(f"=== Iteration {self.iteration + 1} ===")
            result = await self.send_auth_request()
            logging.info(f"Result: {result}")

            self.iteration += 1

        logging.info("Monitor completed all iterations")


async def main():
    """Main function to run the auth monitor."""
    import argparse

    parser = argparse.ArgumentParser(description="Authentication Monitor")
    parser.add_argument(
        "--interval", type=int, default=1, help="Base interval in minutes (default: 1)"
    )
    parser.add_argument(
        "--max-iterations", type=int, help="Maximum number of iterations (default: unlimited)"
    )
    parser.add_argument("--endpoint", type=str, help="Authentication endpoint URL")

    args = parser.parse_args()

    # Override endpoint if provided
    if args.endpoint:
        os.environ["AUTH_ENDPOINT"] = args.endpoint

    try:
        monitor = AuthMonitor(
            base_interval_minutes=args.interval, max_iterations=args.max_iterations
        )
        await monitor.run_monitor()
    except KeyboardInterrupt:
        logging.info("Monitor stopped by user")
    except Exception as e:
        logging.error(f"Monitor failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
