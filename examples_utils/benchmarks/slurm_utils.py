# Copyright (c) 2022 Graphcore Ltd. All rights reserved.

import atexit
from datetime import timedelta
import subprocess
import os
import time
import logging
from typing import Tuple
from io import TextIOWrapper
import sys
import textwrap

from examples_utils.benchmarks.command_utils import (get_poprun_config, get_num_ipus, query_option_in_cmd)

# Get the module logger
logger = logging.getLogger()


def configure_slurm_job_working_directory(job_wd):
    return f"cd {job_wd}\n"


def configure_slurm_python_command(cmd):
    python_index = query_option_in_cmd(cmd, ["python", "python3"])
    return " ".join(cmd[python_index:]) + "\n"


def configure_slurm_sdk_and_venv(args):
    # TODO: pull SDK via popsdk?
    # TODO: recreate python venv?
    bash_script = f"source {os.path.join(args.sdk_path, 'enable')}\n"
    bash_script += f"source {os.path.join(args.venv_path, 'bin', 'activate')}"
    return bash_script + "\n"


def configure_slurm_ipu_partition(poprun_config, num_ipus):
    # TODO: support recreation of clusters for jobs that require more than one ild

    bash_script = textwrap.dedent("""
    export IPUOF_VIPU_API_HOST=angelsfall-ctrl
    export IPUOF_VIPU_API_PORT=8090
    export IPUOF_VIPU_API_PARTITION_ID=p${SLURM_JOB_ID}
    export ALLOCATION=c${SLURM_JOB_ID}
    """)

    if poprun_config == {}:
        bash_script += ("\nvipu create partition $IPUOF_VIPU_API_PARTITION_ID"
                        f" --allocation $ALLOCATION --size {num_ipus} --reconfigurable\n")
    else:
        num_instances = 1
        if poprun_config["num_instances"] is not None:
            num_instances = int(poprun_config["num_instances"])
        num_hosts = 1
        if poprun_config["host"] is not None:
            num_hosts = len(poprun_config["host"])

        # reconfigure number of instances per host before moving to the next host
        bash_script += f"\nexport SLURM_NTASKS_PER_NODE={int(num_instances / num_hosts)}\n"

        # reconfigure the host set to be used for the job
        bash_script += f"NUM_HOSTS={num_hosts}\n"
        bash_script += textwrap.dedent("""
        BASE=$(echo $SLURM_JOB_NODELIST  | cut -d '-' -f 1,2)
        if [ "${SLURM_JOB_NODELIST/[/}" == "${SLURM_JOB_NODELIST}" ]
        then NODELIST=$SLURM_JOB_NODELIST
        else
            #echo base=$BASE
            NODERANGE=$(echo $SLURM_JOB_NODELIST | cut -d '-' -f 3,4,5,6 | sed -e "s/\[/{/" -e "s/\-/../g" -e "s/\]/}/" -e "s/,/} {/")
            RAWNODELIST=$(sed "s/{/$BASE-{/g" <<< $NODERANGE )
            #echo raw $RAWNODELIST
            NODELIST=$(eval echo $(echo $RAWNODELIST))
        fi
        #echo node $NODELIST
        COUNT=$(echo $NODELIST | wc -w)
        SKIP=$((COUNT/NUM_HOSTS))
        I=0
        read -a NA <<< $NODELIST
        HOSTS=""
        while [ $I -lt $((COUNT+1)) ]
        do
            HOSTS="$HOSTS,${NA[$I]}"
            I=$(($I+$SKIP))
        done
        HOSTS=$(sed -e 's/^,//g' -e 's/,$//g' <<<$HOSTS)
        echo $HOSTS

        export SLURM_JOB_NODELIST=$HOSTS
        """)

        # add poprun options
        bash_script += "poprun "
        bash_script += f" --host=$SLURM_JOB_NODELIST --num-instances={num_instances}"
        bash_script += f" --vipu-allocation=$ALLOCATION "
        bash_script += poprun_config["other_args"] + " "

        if num_hosts > 1:
            # TODO handling for multi host options
            # synchronise python venv, poplar sdk distribute ssh keys
            # migrate tcp_if_include to --host-subnet parameter instead
            pass

    return bash_script


def configure_slurm_job(args, cmd, variant_name, variant_log_dir, job_wd):
    poprun_config = get_poprun_config(args, cmd)
    num_ipus = int(get_num_ipus(variant_name))

    bash_script = "#!/bin/bash\n"
    bash_script += configure_slurm_job_working_directory(job_wd)
    bash_script += configure_slurm_sdk_and_venv(args)
    bash_script += configure_slurm_ipu_partition(poprun_config, num_ipus)
    bash_script += configure_slurm_python_command(cmd)

    job_script_path = os.path.join(variant_log_dir, "submit.sh")

    with open(job_script_path, "w") as script_handle:
        script_handle.write(bash_script)

    stdout_log_path = os.path.join(variant_log_dir, "slurm-%j.out")
    stderr_log_path = os.path.join(variant_log_dir, "slurm-%j.err")

    if num_ipus <= 16:
        submission_script = "runonpod16.sh"
    elif num_ipus <= 64:
        submission_script = "runonpod64.sh"
    elif num_ipus <= 128:
        submission_script = "runonpod128.sh"
    elif num_ipus <= 256:
        submission_script = "runonpod256.sh"
    else:
        err = "Benchmark cannot utilise more than 256 IPUs"
        logging.error(err)
        raise ValueError(err)

    slurm_job_command = [
        submission_script, "--wait", "--job-name", variant_name, "-e", stderr_log_path, "-o", stdout_log_path,
        job_script_path
    ]

    return {
        "cmd": slurm_job_command,
        "stdout_log_path": stdout_log_path,
        "stderr_log_path": stderr_log_path,
        "job_name": variant_name,
        "timeout": args.timeout
    }


def kill_slurm_job(proc, job_name):
    proc.kill()
    logger.error("Slurm job launching process exited abnormally."
                 f" Killing job with job name: {job_name}.")
    proc = subprocess.run(["scancel", "--jobname", job_name],
                          stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,
                          env=os.environ)
    if proc.returncode != 0:
        logger.error(f"Unable to kill slurm job: {job_name}."
                     f"Exit code: {proc.returncode}."
                     f"Reported error: {proc.stderr.decode()}")


def run_and_monitor_progress_on_slurm(cmd: list,
                                      job_name: str,
                                      stdout_log_path: str,
                                      stderr_log_path: str,
                                      listener: TextIOWrapper,
                                      timeout: int = None,
                                      **kwargs) -> Tuple[str, str, int]:

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=80)

    # make sure job is killed if the current process is interrupted or exists unexpectedly
    atexit.register(kill_slurm_job, proc, job_name)

    job_submitted = False
    stdout_path = None
    stderr_path = None

    # make sure job is submitted, and stdout and stderr files are available
    while proc.poll() is None and (stdout_path is None or stderr_path is None):
        if not job_submitted:
            o = proc.stdout.readline().decode()
            if "Submitted" in o:
                job_id = o.split()[-1]
                job_submitted = True
                stdout_log_path = stdout_log_path.replace("%j", job_id)
                stderr_log_path = stderr_log_path.replace("%j", job_id)
                logger.info(f"Slurm Job submitted. Job id: {job_id}. Job name: {job_name}")
        # TODO: error handling when there is a failure to submit the job
        else:
            if os.path.exists(stdout_log_path):
                stdout_path = stdout_log_path
            if os.path.exists(stderr_log_path):
                stderr_path = stderr_log_path

    # TODO: check if the process is still fine here. Process may complete and stdout_path/ stderr_path are None
    outs = [[], []]

    # now read stdout and stderr every 1s while the process is still active
    total_time = 0
    timeout_error = False
    with open(stdout_path, "rb", 80) as stdout, open(stderr_path, "rb", 80) as stderr:
        while proc.poll() is None:

            stdout_data = stdout.read().decode()
            if stdout_data != '':
                outs[0].append(stdout_data)
                listener.write(stdout_data)

            stderr_data = stderr.read().decode()
            if stderr_data != '':
                outs[1].append(stderr_data)
                listener.write(stderr_data)

            listener.flush()

            time.sleep(1)
            total_time += 1

            if timeout is not None and total_time >= timeout:
                logger.error("TIMEOUT")
                timeout_error = True
                proc.kill()
                kill_slurm_job(proc, job_name)
                atexit.unregister(kill_slurm_job)

            sys.stderr.write("\r")
            sys.stderr.write(f"\tBenchmark elapsed time: {str(timedelta(seconds=total_time))} ({total_time} seconds)")
            sys.stderr.flush()

        # read the rest
        outs[0].extend(stdout.readlines())
        listener.write(outs[0][-1])
        outs[1].extend(stderr.readlines())
        listener.write(outs[1][-1])
        listener.flush()

    sys.stderr.write("\r")
    sys.stderr.write("\n")
    stdout_log = "".join(outs[0])
    stderr_log = "".join(outs[1])
    exitcode = proc.returncode

    # slurm job must have finished successfully, so no need to cancel job
    atexit.unregister(kill_slurm_job)

    if timeout_error:
        err += f"\nTimeout ({timeout})\n"

    return stdout_log, stderr_log, exitcode
