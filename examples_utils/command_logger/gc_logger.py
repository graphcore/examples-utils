# Copyright (c) 2022 Graphcore Ltd. All rights reserved.

import ipynbname
import json
import nbformat
import os
import pathlib
import pkg_resources
import psutil
import shlex
import subprocess
import sys
import time

from datetime import datetime


class GCLogger(object):
    _instance = None
    _GC_LOG_STATE = None
    _GC_LOG_CFG_PATH = pathlib.Path.home().joinpath(".graphcore", "logs", f"{datetime.strftime('%Y_%m_%d')}")

    _FAST_POLLING_SECONDS = 10
    _SLOW_POLLING_SECONDS = 60

    _notebook_metadata = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GCLogger, cls).__new__(cls)

            if cls._GC_LOG_STATE is None:
                # request user and save their preferred choice
                print(
                    "\n\n====================================================================================================================================================\n\n"
                    "Graphcore would like to collect information about the applications and code being run in this notebook, as well as the system it's being run on to improve \n"
                    "usability and support for future users. The information will be anonymised and sent to Graphcore \n\n"
                    "You can disable this at any time by running `GCLogger.stop_logging()'`.\n\n"
                    "Unless logging is disabled, the following information will be collected:\n"
                    "\t- User progression through the notebook\n"
                    "\t- Notebook details: number of cells, code being run and the output of the cells\n"
                    "\t- ML application details: Model information, performance, hyperparameters, and compilation time\n"
                    "\t- Environment details: Framework/packages/libraries used, container details\n"
                    "\t- System performance: IO, memory and host compute performance\n\n"
                    "====================================================================================================================================================\n\n"
                )

        return cls._instance

    @classmethod
    def __write_json(cls, dict_to_write, filename, style="w"):
        try:
            with open(cls._GC_LOG_CFG_PATH.joinpath(f"{filename}.json"), style) as outfile:
                json.dump(dict_to_write, outfile)
        except Exception as e:
            sys.stderr.write(f"Config logging error logging to file: {e}")

    @classmethod
    def __log_sysperf_info(cls):
        log_dict = {}

        # Record some constants (CPU count, freq, disk setup)
        log_dict["CPU_count"] = psutil.cpu_count()
        log_dict["CPU_stats"] = str(psutil.cpu_stats())
        log_dict["CPU_freq"] = str(psutil.cpu_freq())
        cls.__write_json(log_dict, cls._GC_LOG_CFG_PATH.joinpath("cpu_info.json"))

        # Collect quick disk performance stats (Disk <-> Host) in background
        with open(cls._GC_LOG_CFG_PATH.joinpath("fio_results.log"), "a") as outfile:
            command = shlex.split(
                "fio --name=random-write --ioengine=posixaio --rw=randwrite "
                "--bs=4k --size=1g --numjobs=1 --iodepth=1 --runtime=5 "
                "--time_based --end_fsync=1"
            )
            subprocess.run(command, stdout=outfile, stderr=outfile)

    @classmethod
    def __log_ipuperf_info(cls):
        # Get information for each IPU available
        with open(cls._GC_LOG_CFG_PATH.joinpath("ipu_perf.json"), "a") as outfile:
            num_ipus = os.getenv("NUM_AVAILABLE_IPU")

            # Host <-> IPU sync latency
            for i in range(num_ipus):
                subprocess.run(shlex.split(f"gc-hostsynclatencytest -d {i} -j"), stdout=outfile, stderr=outfile)

            # Host <-> IPU data transfer
            for i in range(num_ipus):
                subprocess.run(shlex.split(f"gc-hosttraffictest -d {i} -j"), stdout=outfile, stderr=outfile)

            # IPU <-> IPU data transfer
            subprocess.run(shlex.split("gc-iputraffictest --all-links -j"), stdout=outfile, stderr=outfile)

    @classmethod
    def __log_notebook_info(cls):
        # Notebook path
        cls._notebook_metadata = {
            "notebook_path": ipynbname.path(),
        }

        cls.__write_json(cls, cls._notebook_metadata, "notebook_info")

    @classmethod
    def __log_dataset_info(cls):
        # Overwrite old info - likely datasets persist throughout and probably
        # will only increase in size
        while True:
            # Look for everything that looks like a dataset
            # Find location/path

            # Find size

            time.sleep(cls._SLOW_POLLING_SECONDS)

    @classmethod
    def __log_sysperf_metrics(cls):
        while True:
            iteration_dict = {}

            # CPU utilisation
            iteration_dict["timestamp"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            iteration_dict["cpu_percent"] = psutil.cpu_percent()

            # virtual/swap memory usage
            iteration_dict["virtual_memory"] = psutil.virtual_memory().percent
            iteration_dict["swap_memory"] = psutil.swap_memory().percent

            # Disk usage
            iteration_dict["disk_used"] = psutil.disk_usage("/").used

            cls.__write_json(cls, iteration_dict, "sys_perf.json", "a")

            time.sleep(cls._FAST_POLLING_SECONDS)

    @classmethod
    def __log_file_metrics(cls):
        while True:
            # Get all .popef files name and size
            popef_files = pathlib.Path("/tmp/exe_cache").glob("**/*.popef")
            popef_dict = {}
            for file in popef_files:
                popef_dict[str(file)] = file.stat().st_size

            cls.__write_json(cls, popef_dict, "popef_files")

            # Search for all weight files and poll size/name
            weights_extensions = ["onnx", "pt", "pb"]
            weight_files = []
            search_dir = pathlib.Path(cls._notebook_metadata["notebook_path"]).parents[1]
            for ext in weights_extensions:
                weight_files.append(search_dir.glob(f"**/*.{ext}"))

            weight_dict = {}
            for file in weight_files:
                weight_dict[str(file)] = file.stat().st_size

            cls.__write_json(cls, weight_dict, "weight_files")

            # Query pip packages and versions
            pkgs_dict = {i.key: i.version for i in pkg_resources.working_set}
            cls.__write_json(cls, pkgs_dict, "python_packages")

            time.sleep(cls._SLOW_POLLING_SECONDS)

    @classmethod
    def __log_notebook_progression(cls):
        check_timestamp = datetime.now()
        while True:
            with open(pathlib.Path(cls._notebook_metadata["notebook_path"]), "r") as notebook:
                raw_notebook = nbformat.read(notebook, nbformat.NO_CONVERT)

            # Index the cells in the notebook
            cell_indexes = [i for i in range(len(raw_notebook["cells"]))]
            indexed_cells = [(i, j) for i, j in zip(cell_indexes, raw_notebook["cells"])]

            # Find out which code cells were executed since last check
            code_cell_metadata = [
                [cell[0], cell[1]["metadata"].get("execution")]
                for cell in indexed_cells
                if cell[1]["cell_type"] == "code"
            ]
            execution_times = [(x[0], x[1]["iopub.execute_input"]) for x in code_cell_metadata if x[1]]

            # Exclude cells that were executed before last check timestamp
            execution_times = [
                x
                for x in execution_times
                if (datetime.strptime(x[1], "%Y-%m-%dT%H:%M:%S.%fZ") - check_timestamp).total_seconds() > 0
            ]

            # Sort and update our logs
            execution_times.sort(key=lambda x: x[1])
            execution_times = {execution_times[1]: execution_times[0]}

            cls.__write_json(cls, execution_times, "cell_execution_log")

            # Update just before sleeping
            check_timestamp = datetime.now()

            time.sleep(cls._FAST_POLLING_SECONDS)

    @classmethod
    def __log_compile_times(cls):
        """Capture compile time from noteboook.py

        Note: Because of how general this task is, it seems the best we can do
        for now is capture all output that mentions 'compilation' etc. and sift
        through the outputs later.

        If we can get more specificity on how compilation happens, what we can
        expect etc. (HF only, model.compile() explicit calls etc.) then we can
        clean this up a lot and be more particular about what we collect.
        """

        while True:
            compilation_statements = {}

            with open(pathlib.Path(cls._notebook_metadata["notebook_path"])) as notebook:
                raw_notebook = nbformat.read(notebook, nbformat.NO_CONVERT)

            # Get all code cells, search for compile time
            code_cell_outputs = [cell["outputs"] for cell in raw_notebook["cells"] if cell["cell_type"] == "code"]
            for output in code_cell_outputs:
                # Some cells have a seperate 'data' outputs. We need 'text' output
                if len(output) > 1:
                    output = output[1]

                # Get last few chars, should contain the compile time
                text = output.get("text")
                if text is not None and "compil" in text:  # "compil" here is purposeful
                    compilation_statements["timestamp"] = text[-100:]

            cls.__write_json(cls, compilation_statements, "compile_statments", "a")

            time.sleep(cls._SLOW_POLLING_SECONDS)

    @classmethod
    def start_logging(cls):
        if cls._GC_LOG_STATE == "ENABLED":
            return
        cls._GC_LOG_STATE = "ENABLED"

        # Start multiprocess procs for below

        # One-time collection
        # (constant, static information on system/env)
        cls.__log_sysperf_info(cls)
        cls.__log_ipuperf_info(cls)
        cls.__log_notebook_info(cls)
        cls.__log_dataset_info(cls)

        # Frequent polling every cls._FAST_POLLING_SECONDS
        # (changing values, metrics, measurements on system/env)
        cls.__log_sysperf_metrics(cls)
        cls.__log_notebook_progression(cls)

        # Infrequent polling every cls._SLOW_POLLING_SECONDS
        # (names, file sizes, packages etc.)
        cls.__log_file_metrics(cls)
        cls.__log_compile_times(cls)

    @classmethod
    def stop_logging(cls):
        if cls._GC_LOG_STATE == "DISABLED":
            return
        cls._GC_LOG_STATE = "DISABLED"

        # Multiprocess kill logging processes


GCLogger()
