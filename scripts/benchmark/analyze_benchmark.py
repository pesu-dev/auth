"""Script to analyze benchmark CSV output."""

from __future__ import annotations

import argparse
import statistics
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from util import resolve_output_path

if TYPE_CHECKING:
    from pathlib import Path


def analyze_benchmark(df: pd.DataFrame) -> None:
    """Analyze benchmark CSV output and print a summary.

    Args:
        df (pd.DataFrame): One benchmark's results, with `status` and `time` columns, and the
            `start` column benchmark_requests.py writes.
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
    # From the first request's start to the last one's end. Adding up the latencies instead is right
    # only for a sequential run: in a parallel one they overlap, and the sum is many times the run.
    if "start" in df.columns:
        elapsed = (df["start"] + df["time"]).max() - df["start"].min()
        elapsed_note = ""
    else:
        # A CSV from before the start column was written
        elapsed = df["time"].sum()
        elapsed_note = " (sum of latencies: no start times, so only right for a sequential run)"
    throughput = total_requests / elapsed if elapsed else float("inf")

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
    print(f"⏰ Elapsed time         : {elapsed:.3f} sec{elapsed_note}")
    print(f"📊 90th percentile time : {p90:.3f} sec")
    print(f"📊 95th percentile time : {p95:.3f} sec")
    print(f"📊 99th percentile time : {p99:.3f} sec")


def plot_distribution(dfs: list[pd.DataFrame], files: list[str], outfile: Path) -> None:
    """Plot the distribution of response times for each benchmark on the same plot.

    Args:
        dfs (list[pd.DataFrame]): The benchmark DataFrames.
        files (list[str]): The file names.
        outfile (Path): The path to write the plot to.

    Returns:
        None
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
    plt.savefig(outfile, dpi=300)
    print(f"Results saved to: {outfile}")
    plt.close()


def plot_response_time_over_requests(dfs: list[pd.DataFrame], files: list[str], outfile: Path) -> None:
    """Plot the response time over requests for each benchmark on the same plot.

    Args:
        dfs (list[pd.DataFrame]): The benchmark DataFrames.
        files (list[str]): The file names.
        outfile (Path): The path to write the plot to.

    Returns:
        None
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
    plt.savefig(outfile, dpi=300)
    print(f"Results saved to: {outfile}")
    plt.close()


def main() -> None:
    """Summarise and plot benchmark CSV files from the command line."""
    parser = argparse.ArgumentParser(description="Analyze benchmark CSV output.")
    # Required: without it args.files is None and the read below fails with a bare TypeError
    parser.add_argument("--files", "-f", help="Path to the benchmark CSV files", nargs="+", required=True)
    parser.add_argument(
        "--output-dir",
        type=str,
        help="The directory to write plots into (default: benchmark/results at the repository root)",
    )
    parser.add_argument(
        "--tag",
        type=str,
        help="An identifier appended to the generated filenames, for telling runs apart",
    )
    args = parser.parse_args()

    dfs = [pd.read_csv(file) for file in args.files]

    for df in dfs:
        analyze_benchmark(df)
        print("-" * 40)

    for plot, stem in (
        (plot_distribution, "distribution"),
        (plot_response_time_over_requests, "timeline"),
    ):
        plot(
            dfs,
            args.files,
            resolve_output_path(
                script_name=stem,
                extension="png",
                output_dir=args.output_dir,
                tag=args.tag,
            ),
        )


if __name__ == "__main__":
    main()
