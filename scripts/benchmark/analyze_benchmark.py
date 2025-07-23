import argparse
import statistics
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns


def analyze_benchmark(df: pd.DataFrame):
    """
    Analyze benchmark CSV output and print a summary.
    Args:
        df (pd.DataFrame): The benchmark DataFrame.
    """
    total_requests = df.shape[0]
    success_count = df[df["status"] == 1].shape[0]
    failed_count = total_requests - success_count
    success_rate = (success_count / total_requests) * 100

    avg_time = df["time"].mean()
    avg_success_time = df[df["status"] == 1]["time"].mean()

    min_time = df["time"].min()
    max_time = df["time"].max()
    median_time = statistics.median(df["time"])
    total_time = df["time"].sum()
    throughput = total_requests / total_time if total_time else float("inf")

    p90 = np.percentile(df["time"], 90)
    p95 = np.percentile(df["time"], 95)
    p99 = np.percentile(df["time"], 99)

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


def plot_distribution(dfs: list[pd.DataFrame], files: list[str]):
    """
    Plot the distribution of response times for each benchmark on the same plot.
    Args:
        dfs (list[pd.DataFrame]): The benchmark DataFrames.
        files (list[str]): The file names.
    """
    for df, file in zip(dfs, files):
        df["label"] = file
    df = pd.concat(dfs)
    plt.figure(figsize=(10, 6))
    sns.histplot(
        data=df[df["status"] == 1],
        x="time",
        hue="label",
        kde=True,
        bins=30,
        stat="density",
        common_norm=False,
    )
    plt.title("Distribution of Response Times (Success Only)")
    plt.xlabel("Response Time (seconds)")
    plt.ylabel("Density")
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.tight_layout()
    plt.savefig("distribution.png", dpi=300)
    plt.close()


def plot_response_time_over_requests(dfs: list[pd.DataFrame], files: list[str]):
    """
    Plot the response time over requests for each benchmark on the same plot.
    Args:
        dfs (list[pd.DataFrame]): The benchmark DataFrames.
        files (list[str]): The file names.
    """
    plt.figure(figsize=(12, 6))
    for df, file in zip(dfs, files):
        df = df.reset_index().rename(columns={"index": "request"})
        sns.lineplot(data=df, x="request", y="time", label=file, marker="o", linewidth=1)
    plt.title("Response Time Over Requests")
    plt.xlabel("Request Number")
    plt.ylabel("Response Time (seconds)")
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.legend()
    plt.tight_layout()
    plt.savefig("timeline.png", dpi=300)
    plt.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze benchmark CSV output.")
    parser.add_argument("--files", "-f", help="Path to the benchmark CSV files", nargs="+")
    args = parser.parse_args()

    dfs = [pd.read_csv(file) for file in args.files]

    for df in dfs:
        analyze_benchmark(df)
        print("-" * 40)

    plot_distribution(dfs, args.files)
    plot_response_time_over_requests(dfs, args.files)
