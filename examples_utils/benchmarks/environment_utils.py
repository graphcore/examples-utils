# Copyright (c) 2022 Graphcore Ltd. All rights reserved.
from argparse import ArgumentParser
import copy
from io import TextIOWrapper
import logging
import os
from pathlib import Path
import subprocess
import re

# Get the module logger
logger = logging.getLogger(__name__)


def get_mpinum(command: str) -> int:
    """Get num replicas (mpinum) from the cmd.

    Args:
        command (str): The command line that includes a call to mpirun

    Returns:
        mpinum (int): Number of processes passed to mpirun
    
    """

    m = re.search(r"mpirun.+--np.(\d*) ", command)
    if m:
        mpinum = float(m.group(1))
    else:
        mpinum = 1

    return mpinum


def merge_environment_variables(new_env: dict, benchmark_spec: dict) -> dict:
    """Merge existing environment variables with new ones in the benchmark.

    Args:
        new_env (dict): The new environment variables state to merge into 
            current state
        benchmark_dict (dict): The benchmark entry itself in the yaml file

    Returns:
        existing_env (dict): Merged environment state to use for benchmarking
    
    """

    # Build and log the additional ENV variables
    benchmark_env = {}
    if "env" in benchmark_spec:
        benchmark_env = copy.deepcopy(benchmark_spec["env"])
    new_env.update(benchmark_env)

    logger.info(f"Running with the following {len(new_env)} ADDITIONAL ENV variables:")
    for k, v in new_env.items():
        logger.info(f"    {k}={v}")

    # Finally update existing env with new env
    existing_env = os.environ.copy()
    existing_env.update(new_env)

    return existing_env


def run_command(cmd: list, output_stream: TextIOWrapper) -> int:
    """Run a command.

    Args:
        cmd (list): Command to be run
        output_stream (TextIOWrapper): Open file to write stdout/stderr to
    Returns:
        exitcode (int): Exitcode from the subprocess that ran the command

    """

    try:
        exitcode = subprocess.run(cmd, stdout=output_stream,
            stderr=output_stream)

    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed with: {e.output}")
        exitcode = 1

    except Exception as e:
        logger.error(f"Command failed with: {e}")
        exitcode = 1

    return exitcode


def run_remote_command(cmd: list, hostname: list, output_stream: TextIOWrapper) -> int:
    """Run a command remotely on a given host

    Args:
        cmd (list): Command to be run remotely
        hostname (list): Name/IP of the host
        output_stream (TextIOWrapper): Open file to write stdout/stderr to
    Returns:
        exitcode (int): Exitcode from the subprocess that ran the command
    
    """

    remote_cmd = ["ssh", hostname]
    remote_cmd.extend(cmd)

    try:
        exitcode = subprocess.run(remote_cmd, stdout=output_stream,
            stderr=output_stream)

    except subprocess.CalledProcessError as e:
        logger.error(f"Remote command on {hostname} failed with: {e.output}")
        exitcode = 1

    except Exception as e:
        logger.error(f"Remote command on {hostname} failed with: {e}")
        exitcode = 1

    return exitcode


def ssh_copy_id(hostname: str, output_stream: TextIOWrapper) -> int:
    """Copy ssh ID 

    Args:
        cmd (list): Command to be run remotely
        hostname (list): Name/IP of the host
        output_stream (TextIOWrapper): Open file to write stdout/stderr to
    Returns:
        exitcode (int): Exitcode from the subprocess that ran the command
    
    """

    copy_cmd = ["ssh-copy-id", hostname]
    try:
        exitcode = subprocess.run(copy_cmd, stdout=output_stream,
            stderr=output_stream)
    except:
        logger.warning(f"Automated ssh-copy-id failed to {hostname}, "
            "please ensure ssh ids have been copied to all hosts manually "
            "before attempting this benchmark.")
        exitcode = 1

    return exitcode


def create_tmp_dir(hostname: str, output_stream: TextIOWrapper) -> str:
    """Create a temporary directory at a given host.

    Args:
        hostname (list): Name/IP of the host
        output_stream (TextIOWrapper): Open file to write stdout/stderr to
    Returns:
        tmp_dir_path (str): Path to the temporary directory created

    """

    # POSIX spec requires HOME to be set by OS
    tmp_dir_path = str(Path.home().joinpath("benchmarking_tmp_dir"))
    path_create_cmd = ["mkdir", "-p", tmp_dir_path]
    logger.info(f"Creating temporary dir {tmp_dir_path} at {hostname}")
    run_remote_command(path_create_cmd, hostname, output_stream)

    tmp_dir_path = hostname + ":" + tmp_dir_path

    return tmp_dir_path


def sync_file_remotely(hostname: str, source: str, dest: str,
    output_stream: TextIOWrapper):
    """Rsync a directory to a remote destination.

    Args:
        hostname (str): Name/IP of the host
        source (str): Source directory to be synced
        dest (str): Destion parent directory, where source will be
            copied to
        output_stream (TextIOWrapper): Open file to write stdout/stderr to

    """

    # Create Rsync command with progress tracking for logs
    remote_dest = hostname + ":" + dest + "/"
    rsync_cmd = ["rsync", "-au", source, remote_dest]

    logger.info(f"Copying {source} to {remote_dest}")
    run_command(rsync_cmd, output_stream)


def setup_distributed_filesystems(args: ArgumentParser, poprun_hostnames: list):
    """Setup filesystems on all given poprun hosts for distributed instances.

    Args:
        args (ArgumentParser): Arguments provided for this set of benchmarks
        poprun_hostnames (list): Names/IPs of all poprun hosts defined in this 
            benchmark
    
    """

    with open(Path(args.log_dir, "host_setup.log"), "w") as output_stream:
        exitcode = 0
        for hostname in poprun_hostnames:
            ssh_copy_id(hostname, output_stream)

            # Find where examples dir could be
            if Path(args.examples_location, "public_examples").is_dir():
                examples_path = str(Path(args.examples_location, "public_examples"))
            else:
                examples_path = str(Path(args.examples_location, "examples"))

            # Copy examples, sdks and venv dirs to local temp dir
            sync_file_remotely(hostname, examples_path, str(Path.home()), output_stream)
            sync_file_remotely(hostname, args.sdk_path, str(Path.home()), output_stream)
            sync_file_remotely(hostname, args.venv_path, str(Path.home()), output_stream)


def remove_distributed_filesystems(args: ArgumentParser, poprun_hostnames: list):
    """Remove filesystems on all given poprun hosts for distributed instances.

    Args:
        args (ArgumentParser): Arguments provided for this set of benchmarks
        poprun_hostnames (list): Names/IPs of all poprun hosts defined in this 
            benchmark

    """

    tmp_dir_path = Path(os.getenv("HOME")).joinpath("benchmarking_tmp_dir")
    with open(Path(args.log_dir, "host_teardown.log"), "w") as output_stream:
        for hostname in poprun_hostnames:
            remove_tmp_cmd = ["rm", "-rf", tmp_dir_path]
            logger.info(f"Removing {tmp_dir_path} from {hostname}")
            exitcode = run_remote_command(remove_tmp_cmd, hostname, output_stream)
    
        if exitcode:
            logger.warn(f"Temporary benchmarking directory {tmp_dir_path} on "
                "{hostname} could not be removed. Please remove this dir "
                "manually.")
