import argparse
import csv
import statistics
import numpy as np


def analyze_benchmark(csv_file: str):
    """
    Analyze benchmark CSV output and print a summary.
    Args:
        csv_file (str): Path to the benchmark CSV file.
    """
    success = []
    times = []

    with open(csv_file, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                status = int(row["status"])
                time_taken = float(row["time"])
                success.append(status)
                times.append(time_taken)
            except Exception as e:
                print(f"Skipping row due to error: {e}")
    if not times:
        print("No valid benchmark data found.")
        return

    total_requests = len(times)
    success_count = sum(success)
    failed_count = total_requests - success_count
    success_rate = (success_count / total_requests) * 100

    avg_time = sum(times) / total_requests
    successful_times = [t for s, t in zip(success, times) if s == 1]
    avg_success_time = (
        sum(successful_times) / len(successful_times) if successful_times else float("nan")
    )

    min_time = min(times)
    max_time = max(times)
    median_time = statistics.median(times)
    total_time = sum(times)
    throughput = total_requests / total_time if total_time else float("inf")

    p90 = np.percentile(times, 90)
    p95 = np.percentile(times, 95)
    p99 = np.percentile(times, 99)

    print("📊 Benchmark Summary")
    print("-" * 40)
    print(f"🔢 Total requests       : {total_requests}")
    print(f"✅ Successful requests  : {success_count}")
    print(f"❌ Failed requests      : {failed_count}")
    print(f"📈 Success rate         : {success_rate:.2f}%")
    print(f"⏱️  Avg time/request    : {avg_time:.3f} sec")
    print(f"⏱️  Avg time/successful : {avg_success_time:.3f} sec")
    print(f"🔽 Min time             : {min_time:.3f} sec")
    print(f"🔼 Max time             : {max_time:.3f} sec")
    print(f"⏳ Median time          : {median_time:.3f} sec")
    print(f"🚀 Throughput           : {throughput:.2f} requests/sec")
    print(f"⏰ Total time taken     : {total_time:.3f} sec")
    print(f"📊 90th percentile time : {p90:.3f} sec")
    print(f"📊 95th percentile time : {p95:.3f} sec")
    print(f"📊 99th percentile time : {p99:.3f} sec")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze benchmark CSV output.")
    parser.add_argument("--file", help="Path to the benchmark CSV file")
    args = parser.parse_args()
    analyze_benchmark(args.file)
