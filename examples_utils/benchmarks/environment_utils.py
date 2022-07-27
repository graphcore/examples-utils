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

    return tmp_dir_path


def get_sdk_paths(tmp_dir: str) -> tuple:
    """Get the temp activation/enable script paths for the current venv/sdk.

    Args:
        tmp_dir (str): The temporary benchmarking directory where SDKs and
            venvs will be

    Returns:
        poplar_enable_path (str): The path to the enable script for the poplar
            SDK
        popart_enable_path (str): The path to the enable script for the popart
            SDK
        venv_activate_path (str): The path to the activate script for the venv

    """

    sdk_path = os.getenv("POPLAR_SDK_ENABLED")
    if sdk_path is None:
        logger.warn("A SDK does not seem to have been enabled, please ensure "
                    "that the SDK has been enabled in this environment "
                    "and check that the 'POPLAR_SDK_ENABLED' environment "
                    "variable is being set.")
        poplar_enable_path = None
        popart_enable_path = None
    else:
        # We can construct the new sdk path from environment variables
        sdk_parts = sdk_path.split("/")
        poplar_enable_path = "/".join(sdk_parts[sdk_parts.index("sdks"):])
        poplar_enable_path = str(Path(tmp_dir, poplar_enable_path))

        # Popart path can be found easily from here
        popart_enable_path = poplar_enable_path.replace("poplar", "popart")

    venv_path = os.getenv("VIRTUAL_ENV")
    if venv_path is None:
        logger.warn("A virtual environment does not seem to have been "
                    "activated, please ensure that the venv has been activated "
                    " in this environment and check that the "
                    "'POPLAR_SDK_ENABLED' and 'VIRTUAL_ENVIRONMENT' "
                    "environment variable is being set.")
        venv_activate_path = None
    else:
        # We can construct the new venv path from environment variables
        venv_parts = venv_path.split("/")
        venv_activate_path = "/".join(venv_parts[venv_parts.index("venvs"):])
        venv_activate_path = str(Path(tmp_dir, venv_activate_path))

    return (poplar_enable_path, popart_enable_path, venv_activate_path)


def setup_distributed_filesystems(args: ArgumentParser, poprun_hostnames: list):
    """Setup filesystems on all given poprun hosts for distributed instances.

    Args:
        args (ArgumentParser): Arguments provided for this set of benchmarks
        poprun_hostnames (list): Names/IPs of all poprun hosts defined in this 
            benchmark
    
    """

    # Get SDK/venv paths
    poplar_enable_path, popart_enable_path, venv_activate_path = get_sdk_paths()
    venv_activate_path = get_venv_activate_path()

    with open(Path(args.log_dir, "host_setup.log"), "w") as output_stream:
        for hostname in poprun_hostnames:
            ssh_copy_id(hostname, output_stream)

            # Create local temp dir
            host_tmp_dir = create_tmp_dir(hostname, output_stream)

            # Find where examples dir could be
            if Path(args.examples_location, "public_examples").is_dir():
                examples_path = str(Path(args.examples_location, "public_examples"))
            else:
                examples_path = str(Path(args.examples_location, "examples"))

            # Copy examples, sdks dirs to local temp dir
            rsync_examples_cmd = ["rsync", "-az", examples_path, host_tmp_dir + "/"]
            logger.info(f"Copying {examples_path} to {hostname}")
            exitcode = run_remote_command(rsync_examples_cmd, hostname, output_stream)
            if exitcode: failed_dir = "examples"

            rsync_sdk_cmd = ["rsync", "-az", args.sdk_path, host_tmp_dir + "/"]
            logger.info(f"Copying {args.sdk_path} to {hostname}")
            exitcode = run_remote_command(rsync_sdk_cmd, hostname, output_stream)
            if exitcode: failed_dir = "sdk"

            # Activate venvs remotely and instally requirements
            rsync_venv_cmd = ["source", poplar_enable_path, "&&",
                              "source", popart_enable_path, "&&",
                              "source", venv_activate_path, "&&",
                              "pip", "install", "-r", args.requirements_file]
            logger.info(f"Activating SDK {sdk_name} on {hostname} and "
                        f"installing requirements from {args.requirements_file}")
            exitcode = run_remote_command(rsync_venv_cmd, hostname, output_stream)
            if exitcode: failed_dir = "venv"

            if exitcode:
                logger.error(f"Failed to create {host_tmp_dir}/{failed_dir} "
                    f"on {hostname}. Please create this manually.")


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
