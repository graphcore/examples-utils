import argparse
import csv
import subprocess
import yaml
from getpass import getpass
from pathlib import Path


HEADER_METRICS = ["benchmark name", "variant_name", "throughput", "latency", "total_compiling_time"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--spec",
        required=True,
        type=str,
        help="Path to yaml file with benchmark spec",
    )
    parser.add_argument(
        "--sdk-path",
        required=True,
        type=str,
        help="Path to the SDK root dir used for benchmarking",
    )
    args = parser.parse_args()

    benchmarks = yaml.load(open(args.spec).read(), Loader=yaml.FullLoader)
    
    # Write all results into a common CSV
    with open(Path(args.log_dir, "assessment_results.csv"), "w") as common_file:
        # Use a fixed set of headers
        common_writer = csv.writer(common_file, quoting=csv.QUOTE_ALL)
        common_writer.writerow(HEADER_METRICS)

        # Run all benchmarks 
        for name, setup in benchmarks.items():
            if setup.get("additional_dir") is None:
                setup["additional_dir"] = ""

            # Formulate command for each benchmark
            benchmark_cmd = [
                "bash",
                "./assess_platform.sh",
                args.sdk_path,
                setup["application_name"],
                setup["benchmark"],
                setup["build_steps"],
                setup["additional_dir"],
            ]

            # Run benchmark in a poplar SDK enabled environment
            with open(f"./{name}.log", "w") as output_stream:
                subprocess.run(
                    benchmark_cmd,
                    stdout=output_stream,
                    stderr=output_stream,
                )
            
            # Merge CSV outputs from this benchmark into the common CSV
            with open(Path(f"/tmp/{setup['application_name']}_logs/benchmark_results.csv"), "r") as benchmark_csv:
                # Skip header
                benchmark_reader = csv.reader(benchmark_csv)
                _ = next(benchmark_reader)

                # Include all results rows
                for row in benchmark_reader:
                    common_writer.writerow(row)
