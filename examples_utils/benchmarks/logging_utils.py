# Copyright (c) 2022 Graphcore Ltd. All rights reserved.
import argparse
import csv
from distutils.command.upload import upload
import glob
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from time import time

# Attempt to import wandb silently, if app being benchmarked has required it
WANDB_AVAILABLE = True
try:
    import wandb
except:
    WANDB_AVAILABLE = False

# Get the module logger
logger = logging.getLogger(__name__)

def configure_logger(args: argparse.ArgumentParser):
    """Setup the benchmarks runner logger

    Args:
        args (argparse.ArgumentParser): Argument parser used for benchmarking
    
    """

    # Setup dir
    if not args.log_dir:
        time_str = datetime.fromtimestamp(time()).strftime("%Y-%m-%d-%H.%M.%S.%f")
        args.log_dir = Path(os.getcwd(), f"log_{time_str}").resolve()
    else:
        args.log_dir = Path(args.log_dir).resolve()

    if not args.log_dir.exists():
        args.log_dir.mkdir(parents=True)

    # Setup logger
    logger = logging.getLogger()
    formatter = logging.Formatter("[%(levelname)s] %(asctime)s: %(message)s", "%Y-%m-%d %H:%M:%S")
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(args.logging)

    logger.info(f"Logging directory: '{args.log_dir}'")


def print_benchmark_summary(results: dict):
    """Print a summary of all benchmarks run.

    Args:
        results (dict): Benchmark results dict to create summary from
    
    """

    # Print PASS/FAIL statements
    summary = []
    passed, failed = 0, 0
    for benchmark, variants in results.items():
        for variant in variants:
            if variant.get("exitcode") == 0:
                summary.append(f"PASSED {benchmark}::" f"{variant['benchmark_name']}")
                passed += 1
            else:
                summary.append(f"FAILED {benchmark}::" f"{variant['benchmark_name']}")
                failed += 1

    if summary:
        print("=================== short test summary info ====================\n")
        print("\n".join(summary) + "\n")
        print(f"================ {failed} failed, {passed} passed ===============")


def get_checkpoint_dir(cmd: list):
    """Get the root dir where checkpoints are storied for a model.

    Args:
        cmd (str): The command used for this model run (benchmark)
    """
    
    # List of possible keywords to look for in an argument passed to examples
    checkpoint_keywords = ["checkpoint", "ckpt"]
    path_keywords = ["dir", "path", "location"]

    cmd_args = cmd.split(" --")

    # Look at each arg to see if it could be a checkpoint path
    for arg in cmd_args:
        is_checkpoint_arg = any([x in arg for x in checkpoint_keywords])
        is_path_arg = any([x in arg for x in path_keywords])

        if is_checkpoint_arg and is_path_arg:
            checkpoint_dir = arg.replace("=", " ").split(" ")[1]
            break

    return checkpoint_dir


def get_latest_checkpoint_path(checkpoint_root_dir: str):
    """Get the path to the latest available checkpoint for a model.

    Args:
        checkpoint_root_dir (str): The directory where checkpoints are saved
    """

    # Find all directories in checkpoint root dir
    list_of_dirs = filter(os.path.isdir, glob.glob(checkpoint_root_dir + "/**"))
    print(list(list_of_dirs))
    
    # Sort list of files based on last modification time and take latest
    time_sorted_dirs = sorted(list_of_dirs, key=os.path.getmtime, reverse=True)
    latest_checkpoint_path = time_sorted_dirs[0]

    return latest_checkpoint_path


def get_wandb_link(stderr: str) -> str:
    """Get a wandb link from stderr if it exists.
    """

    wandb_link = None
    for line in stderr.split("\n"):
        if "https://wandb.sourcevertex.net" in line and "/runs/" in line:
            wandb_link = "https:/" + line.split("https:/")[1]
            wandb_link = wandb_link.replace("\n", "")

    return wandb_link


def save_results(log_dir: str, results: dict):
    """Save benchmark results into files.

    Args:
        log_dir (str): The path to the logging directory
        results (dict): The results for this benchmark
    """
    # Save results dict as JSON
    json_filepath = Path(log_dir, "benchmark_results.json")
    with open(json_filepath, "w") as json_file:
        json.dump(results, json_file, sort_keys=True, indent=2)
    logger.info(f"Results saved to {str(json_filepath)}")

    # Parse summary into CSV and save in logs directory
    csv_metrics = ["throughput", "latency", "total_compiling_time"]
    csv_filepath = Path(log_dir, "benchmark_results.csv")
    with open(csv_filepath, "w") as csv_file:
        writer = csv.writer(csv_file, quoting=csv.QUOTE_ALL)
        # Use a fixed set of headers, any more detail belongs in the JSON file
        writer.writerow(["benchmark name", "Variant name"] + csv_metrics)

        # Write a row for each variant
        for benchmark, result in results.items():
            for r in result:
                csv_row = [benchmark, r["variant_name"]]

                # Find all the metrics we have available from the list defined
                for metric in csv_metrics:
                    value = list(r["results"].get(metric, {0: None}).values())[0]
                    if value is not None:
                        value = float(value)
                    csv_row.append(value)

                writer.writerow(csv_row)
    logger.info(f"Results saved to {str(csv_filepath)}")


def upload_checkpoints(upload_targets: list, checkpoint_path: str,
    run_name: str, stderr: str):
    """Upload checkpoints from model run to 

    Args:
        upload_targets (list):
        checkpoint_path (str):
        run_name (str):
        stderr (str): 
    """

    if "wandb" in upload_targets:
        try:
            # Extract info from wandb link
            wandb_link = get_wandb_link(stderr)
            link_parts = wandb_link.split("/")

            run = wandb.init(project=link_parts[-3], id=link_parts[-1], resume="allow")
            artifact = wandb.Artifact(name=run_name + "-checkpoint", type="model")
            artifact.add_dir(checkpoint_path)

            run.log_artifact(artifact, aliases="convergence testing")
        except:
            logger.info("failed to archive checkpoint on wandb")
    
    if "s3" in upload_targets:
        # Placeholder
        pass


def upload_compile_time(wandb_link: str, results: dict):
    """Upload compile time results to a wandb link

    Args:
        wandb_link (str): The link to the W&B run for this benchmark
        results (dict): The results for this benchmark
    """

    # Re-initialise link to allow uploading again
    link_parts = wandb_link.split("/")
    run = wandb.init(project=link_parts[-3], id=link_parts[-1], resume="allow")

    run.log({"Total compile time": results["total_compiling_time"]["mean"]})
