# Copyright (c) 2022 Graphcore Ltd. All rights reserved.

import ipynbname
import json
import nbformat
import os
import pkg_resources
import psutil
import shlex
import subprocess
import sys
import time
import multiprocessing as mp


from datetime import datetime
from pathlib import Path


class GCLogger(object):
    _instance = None
    _GC_LOG_STATE = None
    _GC_LOG_PATH = Path("/notebooks").joinpath("gc_logs", f"{datetime.now().strftime('%Y_%m_%d')}")

    _FAST_POLLING_SECONDS = 10
    _SLOW_POLLING_SECONDS = 60

    _proc_list = []

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GCLogger, cls).__new__(cls)

            if cls._GC_LOG_STATE is None:
                # request user and save their preferred choice
                print(
                    "\n\===========================================================================================================================================\n"
                    "Graphcore would like to collect information about the applications and code being run in this notebook, as well as the system it's being run \n"
                    "on to improve usability and support for future users. The information will be anonymised and sent to Graphcore \n\n"
                    "You can disable this at any time by running `GCLogger.stop_logging()'`.\n\n"
                    "Unless logging is disabled, the following information will be collected:\n"
                    "\t- User progression through the notebook\n"
                    "\t- Notebook details: number of cells, code being run and the output of the cells\n"
                    "\t- ML application details: Model information, performance, hyperparameters, and compilation time\n"
                    "\t- Environment details\n"
                    "\t- System performance: IO, memory and host compute performance\n\n"
                    f"You can view the information being collected at: {cls._GC_LOG_PATH}\n"
                    "=============================================================================================================================================\n"
                )

                cls._GC_LOG_PATH.mkdir(parents=True, exist_ok=True)

        return cls._instance

    @classmethod
    def __write_json(cls, dict_to_write, filename, mode="w"):

        try:
            json_path = cls._GC_LOG_PATH.joinpath(f"{filename}.json")

            with open(json_path, mode) as outfile:
                json.dump(dict_to_write, outfile)

        except Exception as e:
            sys.stderr.write(f"Config logging error logging to file: {e}")

    @classmethod
    def __log_sysperf_info(cls):
        if cls._GC_LOG_STATE == "DISABLED":
            return

        log_dict = {}

        # Record some constants (CPU count, freq, disk setup)
        log_dict["CPU_count"] = psutil.cpu_count()
        log_dict["CPU_stats"] = str(psutil.cpu_stats())
        log_dict["CPU_freq"] = str(psutil.cpu_freq())
        cls.__write_json(log_dict, "cpu_info")

        # Collect quick disk performance stats (Disk <-> Host) in background

    #         with open(cls._GC_LOG_PATH.joinpath("fio_results.log"), "w") as outfile:
    #             command = (
    #                 "apt update"
    #                 "&& apt install -y fio "
    #                 "&& fio --name=random-write --ioengine=posixaio --rw=randwrite "
    # -               "--bs=4k --size=1g --numjobs=1 --iodepth=1 --runtime=5 "
    # -               "--time_based --end_fsync=1""
    #             )
    #             subprocess.run(command, stdout=outfile, stderr=outfile, shell=True)

    #         # Clean up files from profiling
    #         cls._GC_LOG_PATH.parent.joinpath("random-write.0.0").unlink()

    @classmethod
    def __log_ipuperf_info(cls):
        if cls._GC_LOG_STATE == "DISABLED":
            return

        # Get information for each IPU available
        with open(cls._GC_LOG_PATH.joinpath("ipu_perf.json"), "a") as outfile:
            num_ipus = int(os.getenv("NUM_AVAILABLE_IPU"))

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
        if cls._GC_LOG_STATE == "DISABLED":
            return

        notebook_metadata = {
            "notebook_path": str(ipynbname.path()),
        }

        cls.__write_json(notebook_metadata, "notebook_info")

    @classmethod
    def __log_dataset_info(cls):
        # Overwrite old info - likely datasets persist throughout and probably
        # will only increase in size
        while True:
            if cls._GC_LOG_STATE == "DISABLED":
                return

            # Look for everything that looks like a dataset
            # Find location/path

            # Find size

            time.sleep(cls._SLOW_POLLING_SECONDS)

    @classmethod
    def __log_sysperf_metrics(cls):
        while True:
            if cls._GC_LOG_STATE == "DISABLED":
                return

            iteration_dict = {}

            # CPU utilisation
            iteration_dict["timestamp"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            iteration_dict["cpu_percent"] = psutil.cpu_percent()

            # virtual/swap memory usage
            iteration_dict["virtual_memory"] = psutil.virtual_memory().percent
            iteration_dict["swap_memory"] = psutil.swap_memory().percent

            # Disk usage
            iteration_dict["disk_used"] = psutil.disk_usage("/").used

            cls.__write_json(iteration_dict, "sys_perf", "a")

            time.sleep(cls._FAST_POLLING_SECONDS)

    @classmethod
    def __log_file_metrics(cls):
        while True:
            if cls._GC_LOG_STATE == "DISABLED":
                return

            # Find default exe dir, or look locally
            local_path = ipynbname.path().parents[1]
            exe_cache = os.getenv("POPLAR_EXECUTABLE_CACHE_DIR", local_path)

            # Get all .popef files name and size
            popef_files = Path(exe_cache).glob("**/*.popef")
            popef_dict = {}
            for file in popef_files:
                popef_dict[str(file)] = file.stat().st_size

            cls.__write_json(popef_dict, "popef_files")

            # Find default weights/checkpoints dir, or look locally
            weights_cache = os.getenv("CHECKPOINT_DIR", local_path)

            # Search for all weight files and poll size/name
            weights_extensions = ["onnx", "pt", "pb"]
            weight_files = []
            for ext in weights_extensions:
                weight_files.extend(Path(weights_cache).glob(f"**/*.{ext}"))

            weight_dict = {}
            for file in weight_files:
                weight_dict[str(file)] = file.stat().st_size

            cls.__write_json(weight_dict, "weight_files")

            # Query pip packages and versions
            pkgs_dict = {i.key: i.version for i in pkg_resources.working_set}
            cls.__write_json(pkgs_dict, "python_packages")

            time.sleep(cls._SLOW_POLLING_SECONDS)

    @classmethod
    def __log_notebook_progression(cls):
        check_timestamp = datetime.now()
        while True:
            if cls._GC_LOG_STATE == "DISABLED":
                return

            with open(ipynbname.path(), "r") as notebook:
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

            execution_times = [(x[0], x[1].get("iopub.execute_input")) for x in code_cell_metadata if x[1] is not None]

            # Exclude cells that were executed before last check timestamp
            execution_times = [
                x
                for x in execution_times
                if x[1] is not None
                and (datetime.strptime(x[1], "%Y-%m-%dT%H:%M:%S.%fZ") - check_timestamp).total_seconds() > 0
            ]

            # Sort and update our logs
            execution_times.sort(key=lambda x: x[1])
            execution_times = {x[1]: x[0] for x in execution_times}

            if execution_times:
                cls.__write_json(execution_times, "cell_execution_log", "a")

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
            if cls._GC_LOG_STATE == "DISABLED":
                return

            compilation_statements = {}

            with open(ipynbname.path()) as notebook:
                raw_notebook = nbformat.read(notebook, nbformat.NO_CONVERT)

            # Get all code cells, search for compile time
            code_cell_outputs = [cell["outputs"] for cell in raw_notebook["cells"] if cell["cell_type"] == "code"]
            for output in code_cell_outputs:
                # Some cells have a seperate 'data' outputs. We need 'text' output
                if len(output) > 1:
                    output = output[1]

                if output:
                    try:
                        text = output[0].get("text")
                        if text is not None and "compil" in text:  # "compil" here is purposeful
                            compilation_statements[datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ")] = text[-100:]
                    except:
                        continue

            if compilation_statements:
                cls.__write_json(compilation_statements, "compile_statments", "a")

            time.sleep(cls._SLOW_POLLING_SECONDS)

    @classmethod
    def start_logging(cls):
        if cls._GC_LOG_STATE == "ENABLED":
            print("GCLogger is already logging")
            return
        cls._GC_LOG_STATE = "ENABLED"

        background_functions = [
            # One-time collection
            # (constant, static information on system/env)
            cls.__log_sysperf_info,
            cls.__log_ipuperf_info,
            cls.__log_notebook_info,
            cls.__log_dataset_info,
            # Frequent polling every cls._FAST_POLLING_SECONDS
            # (changing values, metrics, measurements on system/env)
            cls.__log_sysperf_metrics,
            cls.__log_notebook_progression,
            # Infrequent polling every cls._SLOW_POLLING_SECONDS
            # (names, file sizes, packages etc.)
            cls.__log_file_metrics,
            cls.__log_compile_times,
        ]

        # Start multiprocess procs for below
        cls._proc_list = [i for i in range(len(background_functions))]
        for i, func in enumerate(background_functions):
            cls._proc_list[i] = mp.Process(
                target=func,
            )
            cls._proc_list[i].daemon = True
            cls._proc_list[i].start()

    @classmethod
    def stop_logging(cls):
        if cls._GC_LOG_STATE == "DISABLED":
            print("GCLogger has already stopped logging")
            return
        cls._GC_LOG_STATE = "DISABLED"

        # Multiprocess kill logging processes
        for i in range(len(cls._proc_list)):
            cls._proc_list[i].terminate()
            cls._proc_list[i].join()

        print("GCLogger has stopped logging")


GCLogger()
