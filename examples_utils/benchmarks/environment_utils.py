# Copyright (c) 2022 Graphcore Ltd. All rights reserved.
import copy
from io import TextIOWrapper
import logging
import os
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


def run_remote_command(cmd: list, hostname: list,
    output_stream: TextIOWrapper) -> int:
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

    exitcode = 0
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


def ssh_copy_id(poprun_hostnames: list, output_stream: TextIOWrapper) -> int:
    """Copy ssh ID 

    Args:
        cmd (list): Command to be run remotely
        poprun_hostnames (list): Names/IPs of all poprun hosts defined in this 
            benchmark
        output_stream (TextIOWrapper): Open file to write stdout/stderr to
    Returns:
        exitcode (int): Exitcode from the subprocess that ran the command
    
    """

    for hostname in poprun_hostnames:
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


def create_tmp_dir(hostname: str) -> str:
    """Create a temporary directory at a given host.

    Args:
        hostname (list): Name/IP of the host
    
    Returns:
        tmp_dir_path (str): Path to the temporary directory created

    """

    user_home_dir = os.getenv("HOME")
    if user_home_dir is None:
        logger.warning("HOME environment variable not set. Attempting to "
            "create temporary benchmarking directory in current wroking "
            "directory.")

    return tmp_dir_path


def get_tmp_dir(hostname: str):
    """Find the benchmarking tmp directory path at a given host.

    Args:
        hostname (list): Name/IP of the host
    
    Returns:
        tmp_dir_path (str): Path to the temporary directory

    """

    return tmp_dir_path


def setup_distributed_filesystems(poprun_hostnames: list, log_dir: str):
    """Setup filesystems on all given poprun hosts for distributed instances.

    Args:
        poprun_hostnames (list): Names/IPs of all poprun hosts defined in this 
            benchmark
    
    """

    with open(log_dir + "\host_setup.log", "w") as process_output:
        ssh_copy_id(poprun_hostnames, process_output)

        for hostname in poprun_hostnames:
            # Create local temp dir
            host_tmp_dir = create_tmp_dir(hostname)

            # Copy examples, sdks and venvs dirs to local temp dir
            rsync_examples_cmd = ["rsync", "-az", examples_path, host_tmp_dir]
            exitcode = run_remote_command(rsync_examples_cmd, hostname, process_output)
            if exitcode: failed_dir = "examples"

            rsync_sdk_cmd = ["rsync", "-az", sdk_path, host_tmp_dir]
            exitcode = run_remote_command(rsync_sdk_cmd, hostname, process_output)
            if exitcode: failed_dir = "sdk"
            
            rsync_venv_cmd = ["rsync", "-az", venv_path, host_tmp_dir]
            exitcode = run_remote_command(rsync_venv_cmd, hostname, process_output)
            if exitcode: failed_dir = "venv"

            if exitcode:
                logger.error()


            


def remove_distributed_filesystems(poprun_hostnames: list, log_dir: str):
    """Remove filesystems on all given poprun hosts for distributed instances.

    Args:
        poprun_hostnames (list): Names/IPs of all poprun hosts defined in this 
            benchmark
    
    """

    with open(log_dir + "\host_teardown.log", "w") as process_output:
        for hostname in poprun_hostnames:
            remove_tmp_cmd = ["rm", "-rf", get_tmp_dir(hostname)]
            exitcode = run_remote_command(remove_tmp_cmd, hostname, process_output)
