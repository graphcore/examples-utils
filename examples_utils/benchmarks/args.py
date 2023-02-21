import argparse


def benchmarks_parser(parser: argparse.ArgumentParser):
    """Add benchmarking arguments to argparse parser"""

    # Key arguments
    parser.add_argument(
        "--additional-metrics",
        action="store_true",
        help="Collect additional metrics to the output CSV file",
    )
    parser.add_argument(
        "--spec",
        type=str,
        nargs="+",
        default=["./benchmarks.yml"],
        help="Yaml files with benchmark spec",
    )
    parser.add_argument(
        "--benchmark",
        type=str,
        nargs="+",
        help="List of benchmark ids to run",
    )

    # Additional functionality controls
    parser.add_argument(
        "--allow-wandb",
        action="store_true",
        help="Allow any wandb commands (do not automatically remove them)",
    )
    parser.add_argument(
        "--compile-only",
        action="store_true",
        help="Enable compile only options in compatible models",
    )
    parser.add_argument(
        "--csv-metrics",
        type=str,
        nargs="+",
        default=tuple(),
        help="List of extra metrics to capture in the CSV output.",
    )
    parser.add_argument(
        "--custom-metrics-files",
        type=str,
        nargs="+",
        help="List of python files containing extra metrics functions.",
    )
    parser.add_argument(
        "--include-convergence",
        action="store_true",
        help=(
            "Include convergence tests (name ending in '_conv') in the set "
            "of benchmarks being run. This only has any effect if "
            "convergence tests would be run anyway i.e. if there are "
            "convergence benchmarks in the yaml file provided in '--spec' or "
            "if the convergence test required is named explicitly in "
            "'--benchmarks'."
        ),
    )
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help=("Stop on the first error and terminate all runs, instead of " "proceeding to the next benchmark"),
    )
    parser.add_argument(
        "--log-dir",
        default=None,
        type=str,
        help="Folder to place log files",
    )
    parser.add_argument(
        "--logging",
        choices=["DEBUG", "INFO", "ERROR", "CRITICAL", "WARNING"],
        default="INFO",
        help=("Specify the logging level set for poplar/popart (the example " "itself, not this benchmarking module"),
    )
    parser.add_argument(
        "--no-code-sync",
        action="store_true",
        help=("Disable automatic syncing of venv/code files across all hosts " "in multi-host benchmarks."),
    )
    parser.add_argument(
        "--profile",
        action="store_true",
        help=(
            "Enable profiling for the benchmarks, setting the appropriate "
            "environment variables and storing profiling reports in the cwd"
        ),
    )
    parser.add_argument(
        "--gc-monitor",
        action="store_true",
        help=("Enable usage monitoring during benchmarks. when set, runs " "gc-monitor every 5 seconds"),
    )
    parser.add_argument(
        "--remove-dirs-after",
        action="store_true",
        help=(
            "Whether or not to remove all directories used for benchmarking "
            "from all hosts involved after the benchmark is complete. This "
            "includes the examples, SDKs and venvs directories."
        ),
    )
    parser.add_argument(
        "--requirements-file",
        default=str(Path.cwd().joinpath("requirements.txt")),
        type=str,
        help=(
            "Path to the application's requirements file. Should only be "
            "manually provided if requested by this benchmarking module. "
            "Defaults to the parent dir of the benchmarks.yml file."
        ),
    )
    parser.add_argument(
        "--timeout",
        default=None,
        type=int,
        help="Maximum time allowed for any benchmark/variant (in seconds)",
    )
    parser.add_argument(
        "--upload-checkpoints",
        default="",
        type=str,
        nargs="+",
        choices=["wandb", "s3"],
        help="List of locations to upload model checkpoints to",
    )

    parser.add_argument("--submit-on-slurm", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--slurm-machine-type", choices=["any", "mk2", "mk2w"], default="any", help=argparse.SUPPRESS)
