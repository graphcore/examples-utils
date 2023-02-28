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


class GCLogger(object):
    _instance = None
    GC_LOG_CFG_PATH = pathlib.Path.home().joinpath(".graphcore", "logs", f"{time.strftime('%Y_%m_%d')}")
    GC_LOG_CFG_FILE = GC_LOG_CFG_PATH.joinpath("config.json")
    GC_LOG_STATE = None

    FAST_POLLING_SECONDS = 10
    SLOW_POLLING_SECONDS = 60

    metrics_dict = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GCLogger, cls).__new__(cls)

            if cls.GC_LOG_STATE is None:
                if cls.GC_LOG_CFG_FILE.is_file():
                    try:
                        with open(cls.GC_LOG_CFG_FILE, "r") as f:
                            config = json.load(f)
                        cls.GC_LOG_STATE = config["GC_LOG_STATE"].upper()
                    except Exception as e:
                        sys.stderr.write(
                            f"Error reading logging config file at {cls.GC_LOG_CFG_FILE.absolute()}. Error: {e}"
                        )
                        cls.GC_LOG_STATE = "DISABLED"
                else:
                    # request user and save their preferred choice
                    message = (
                        "\n\n====================================================================================================================================================\n\n"
                        "Graphcore would like to collect information about the applications and code being run in this notebook, as well as the system it's being run on to improve \n"
                        "usability and support for future users. The information will be anonymised and sent to Graphcore \n\n"
                        "You can disable this at any time by running `GCLogger.LOG_STATE='DISABLED'`.\n\n"
                        "Unless logging is disabled, the following information will be collected:\n"
                        "\t- User progression through the notebook\n"
                        "\t- Notebook details: number of cells, code being run and the output of the cells\n"
                        "\t- ML application details: Model information, performance, hyperparameters, and compilation time\n"
                        "\t- Environment details: Framework/packages/libraries used, container details\n"
                        "\t- System performance: IO, memory and host compute performance\n"
                        "====================================================================================================================================================\n\n"
                    )
                    print(message)

                    config_dict = {"GC_LOG_STATE": "ENABLED"}
                    try:
                        cls.GC_LOG_CFG_PATH.mkdir(parents=True, exist_ok=True)
                        with open(cls.GC_LOG_CFG_FILE, "w") as f:
                            json.dump(config_dict, f)
                    except Exception as e:
                        sys.stderr.write(f"Error creating cloud logging config file. Error: {e}")

        return cls._instance

    @classmethod
    def __write_json(cls, dict, filename, style="w"):
        try:
            with open(cls.GC_LOG_CFG_PATH.joinpath(f"{filename}.json"), style) as outfile:
                json.dump(dict, outfile)
        except Exception as e:
            sys.stderr.write(f"Config logging error logging to file: {e}")

    @classmethod
    def __log_sysperf_info(cls):
        if cls.GC_LOG_STATE == "DISABLED":
            return

        log_dict = {}

        # Record some constants (CPU count, freq, disk setup)
        log_dict["CPU_count"] = psutil.cpu_count()
        log_dict["CPU_stats"] = str(psutil.cpu_stats())
        log_dict["CPU_freq"] = str(psutil.cpu_freq())
        cls.__write_log_file(log_dict, cls.GC_LOG_CFG_PATH.joinpath("cpu_info.log"))

        # Collect quick disk performance stats (Disk <-> Host) in background
        with open(cls.GC_LOG_CFG_PATH.joinpath("fio_results.log"), "a") as outfile:
            command = shlex.split(
                "fio --name=random-write --ioengine=posixaio --rw=randwrite "
                "--bs=4k --size=1g --numjobs=1 --iodepth=1 --runtime=5 "
                "--time_based --end_fsync=1"
            )
            subprocess.run(command, stdout=outfile, stderr=outfile)

    @classmethod
    def __log_ipuperf_info(cls):
        if cls.GC_LOG_STATE == "DISABLED":
            return

        # Get information for each IPU available
        with open(cls.GC_LOG_CFG_PATH.joinpath("ipu_perf.json"), "a") as outfile:
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
    def __log_file_info(cls):
        if cls.GC_LOG_STATE == "DISABLED":
            return

        # Notebook path
        cls.notebook_dict = {
            "notebook_path": ipynbname.path(),
        }

        cls.__write_json(cls, cls.notebook_dict, "notebook_info")

    @classmethod
    def __log_dataset_info(cls):
        if cls.GC_LOG_STATE == "DISABLED":
            return

        # Overwrite old info - likely datasets persist throughout and probably
        # will only increase in size
        while True:
            # Look for everything that looks like a dataset
            # Find location/path

            # Find size

            time.sleep(cls.SLOW_POLLING_SECONDS)

    @classmethod
    def __log_sysperf_metrics(cls):
        if cls.GC_LOG_STATE == "DISABLED":
            return

        while True:
            iteration_dict = {}

            # CPU utilisation
            iteration_dict["cpu_percent"] = psutil.cpu_percent()

            # virtual/swap memory usage
            iteration_dict["virtual_memory"] = psutil.virtual_memory().percent
            iteration_dict["swap_memory"] = psutil.swap_memory().percent

            # Disk usage
            iteration_dict["disk_used"] = psutil.disk_usage("/").used

            cls.metrics_dict[time.time()] = iteration_dict

            time.sleep(cls.FAST_POLLING_SECONDS)

    @classmethod
    def __log_file_metrics(cls):
        if cls.GC_LOG_STATE == "DISABLED":
            return

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
            search_dir = pathlib.Path(cls.notebook_dict["notebook_path"]).parents[1]
            for ext in weights_extensions:
                weight_files.append(search_dir.glob(f"**/*.{ext}"))

            weight_dict = {}
            for file in weight_files:
                weight_dict[str(file)] = file.stat().st_size

            cls.__write_json(cls, weight_dict, "weight_files")

            # Query pip packages and versions
            pkgs_dict = {i.key: i.version for i in pkg_resources.working_set}
            cls.__write_json(cls, pkgs_dict, "python_packages")

            time.sleep(cls.SLOW_POLLING_SECONDS)

    @classmethod
    def __log_notebook_usage(cls):
        if cls.GC_LOG_STATE == "DISABLED":
            return

        while True:
            relevant_outputs = {}

            with open(pathlib.Path(cls.notebook_dict["notebook_path"])) as notebook:
                raw_notebook = nbformat.read(notebook, nbformat.NO_CONVERT)

            # Get all code cells, search for compile time
            code_cell_outputs = [cell["outputs"] for cell in raw_notebook["cells"] if cell["cell_type"] == "code"]
            for output in code_cell_outputs:
                # Some cells have a seperate 'data' outputs. We need 'text' output
                if len(output) > 1:
                    output = output[1]

                text = output.get("text")
                if text is not None and "compil" in text:  # "compil" here is purposeful
                    relevant_outputs[""]

            time.sleep(cls.SLOW_POLLING_SECONDS)

    @classmethod
    def __log_compile_times(cls):
        if cls.GC_LOG_STATE == "DISABLED":
            return

        while True:
            relevant_outputs = {}

            with open(pathlib.Path(cls.notebook_dict["notebook_path"])) as notebook:
                raw_notebook = nbformat.read(notebook, nbformat.NO_CONVERT)

            # Get all code cells, search for compile time
            code_cell_outputs = [cell["outputs"] for cell in raw_notebook["cells"] if cell["cell_type"] == "code"]
            for output in code_cell_outputs:
                # Some cells have a seperate 'data' outputs. We need 'text' output
                if len(output) > 1:
                    output = output[1]

                text = output.get("text")
                if text is not None and "compil" in text:  # "compil" here is purposeful
                    relevant_outputs[""]

            time.sleep(cls.SLOW_POLLING_SECONDS)

    @classmethod
    def start_logging(cls):
        if cls.GC_LOG_STATE == "DISABLED":
            return

        # One-time collection
        # (constant, static information on system/env)
        cls.__log_sysperf_info(cls)
        cls.__log_ipuperf_info(cls)
        cls.__log_file_info(cls)
        cls.__log_dataset_info(cls)

        # Frequent polling every cls.FAST_POLLING_SECONDS
        # (changing values, metrics, measurements on system/env)
        cls.__log_sysperf_metrics(cls)

        # Infrequent polling every cls.SLOW_POLLING_SECONDS
        # (names, file sizes, packages etc.)
        cls.__log_file_metrics(cls)
        cls.__log_notebook_usage(cls)
        cls.__log_compile_times(cls)


GCLogger()
