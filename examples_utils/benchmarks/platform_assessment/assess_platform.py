import argparse
import subprocess
import yaml

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--spec",
        required=True,
        type=str,
        help="Path to yaml file with benchmark spec",
    )
    args = parser.parse_args()

    # Run all benchmarks 
    benchmarks = yaml.load(open(args.spec).read(), Loader=yaml.FullLoader)
    
    for name, setup in benchmarks.items():
        # Formulate command from each benchmark
        benchmark_cmd = [
            "source",
            "./assess_platform.sh",
            setup["application_name"],
            setup["benchmark"],
            setup["build_steps"]
        ]

        # Run benchmark in a poplar SDK enabled environment
        with open(f"./{name}.log", "w") as output_stream:
            subprocess.run(
                benchmark_cmd,
                stdout=output_stream,
                stderr=output_stream,
            )
        
        # Merge CSV outputs into one
