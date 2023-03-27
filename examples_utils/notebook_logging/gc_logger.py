# Copyright (c) 2023 Graphcore Ltd. All rights reserved.

import base64
import boto3
import copy
import hashlib
import ipynbname
import json
import nbformat
import os
import pkg_resources
import subprocess
import time
import multiprocessing as mp


from datetime import datetime
from pathlib import Path


class GCLogger(object):
    _instance = None
    _CREATION_TIME = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    _LOG_STATE = None

    _POLLING_SECONDS = 10

    _MP_MANAGER = mp.Manager()

    _PAYLOAD = _MP_MANAGER.dict()
    _OUTPUT_BUFFER = _MP_MANAGER.dict()

    _PROC_LIST = []

    _BUCKET_NAME = "paperspace-uploading-test-bucket"
    _FIREHOSE_STREAM_NAME = "GCLOGGER_STREAM"
    _FIREHOSE_CLIENT = boto3.client("firehose", region_name="us-east-1")

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GCLogger, cls).__new__(cls)

            if cls._LOG_STATE is None:
                # Request user and save their preferred choice
                print(
                    "\n============================================================================================================================================\n"
                    "Graphcore would like to collect information about the applications and code being run in this notebook, as well as the system it's being run \n"
                    "on to improve usability and support for future users. The information will be anonymised and sent to Graphcore \n\n"
                    "You can disable this at any time by running `GCLogger.stop_logging()'`.\n\n"
                    "Unless logging is disabled, the following information will be collected:\n"
                    "\t- User progression through the notebook\n"
                    "\t- Notebook details: number of cells, code being run and the output of the cells\n"
                    "\t- ML application details: Model information, performance, hyperparameters, and compilation time\n"
                    "\t- Environment details\n"
                    "\t- System performance: IO, memory and host compute performance\n\n"
                    "=============================================================================================================================================\n"
                )

                # Create a short unique user ID
                cls._UNIQUE_HASH = base64.urlsafe_b64encode(
                    hashlib.md5(cls._CREATION_TIME.encode("utf-8")).digest()
                ).decode("ascii")[:12]

                # Help IPython find our custom extension
                extension_path = Path(__file__).parent.joinpath("cell_logger.py").resolve()
                destination_path = Path("/root/.ipython/extensions").resolve()

                subprocess.run(f"cp {extension_path} {destination_path}", shell=True)

                # Create necessary folders for later
                destination_path.joinpath("cell_logs", "errors").mkdir(parents=True, exist_ok=True)

                # Create a firehose delivery stream
                # cls._FIREHOSE_CLIENT.create_delivery_stream(
                #     DeliveryStreamName=cls._FIREHOSE_STREAM_NAME, S3DestinationConfiguration={}  # TODO
                # )

        return cls._instance

    @classmethod
    def __firehose_put(cls):
        """Submit a PUT record request to the firehose stream."""

        while True:
            if cls._LOG_STATE == "DISABLED":
                return

            cls._FIREHOSE_CLIENT.put_record(
                DeliveryStreamName=cls._FIREHOSE_STREAM_NAME, Record=cls._PAYLOAD._getvalue()
            )

            time.sleep(cls._POLLING_SECONDS)

    @classmethod
    def __update_payload(cls, new_output: str, name: str) -> str:
        """Query a method to return its outputs if updated."""

        # Collect latest old and new values
        old_output = cls._OUTPUT_BUFFER[name]

        # Update if values have changed
        if new_output != old_output:
            cls._PAYLOAD[name] = new_output
            cls._OUTPUT_BUFFER[name] = copy.deepcopy(new_output)
        else:
            cls._PAYLOAD[name] = ""

    @classmethod
    def __get_notebook_metadata(cls):
        """Get notebook metadata."""

        while True:
            if cls._LOG_STATE == "disabled":
                return

            notebook_metadata = {
                "notebook_path": str(ipynbname.path()),
                "cluster_id": os.getenv("PAPERSPACE_CLUSTER_ID"),
                "notebook_id": os.getenv("PAPERSPACE_NOTEBOOK_ID"),
                "paperspace_fqdn": os.getenv("PAPERSPACE_FQDN"),
                "paperspace_metric_workload_id": os.getenv("PAPERSPACE_METRIC_WORKLOAD_ID"),
                "repo_id": os.getenv("PAPERSPACE_NOTEBOOK_REPO_ID"),
            }

            for key, val in notebook_metadata.items():
                cls.__update_payload(val, key)

            time.sleep(cls._POLLING_SECONDS)

    @classmethod
    def __get_frameworks_versions(cls) -> str:
        """Get framework versions."""

        frameworks = ["poptorch", "torch"]

        while True:
            if cls._LOG_STATE == "disabled":
                return

            # Query pip packages and versions for frameworks
            all_pkgs = {i.key: i.version for i in pkg_resources.working_set}
            for fw in frameworks:
                cls.__update_payload(all_pkgs.get(fw), f"{fw}_version")

            time.sleep(cls._POLLING_SECONDS)

    @classmethod
    def __get_executables(cls) -> str:
        """Get popef file paths and metadata from wherever possible."""

        # Get all .popef files name and size
        cache_dirs = [
            ipynbname.path().parents[1],  # Local
            os.getenv("POPLAR_EXECUTABLE_CACHE_DIR"),  # HF default
            os.getenv("POPTORCH_CACHE_DIR"),  # Possible for non-HF optimum runs
        ]
        popef_files = []
        popef_file_dumps = {}

        while True:
            if cls._LOG_STATE == "disabled":
                return

            for dir_path in cache_dirs:
                if dir_path:
                    popef_files.extend(Path(dir_path).glob("*.popef"))

            # Analyse the popef file using gc CLI tool
            for file in popef_files:
                proc = subprocess.run(
                    f"popef_dump -m {file}",
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    shell=True,
                    text=True,
                )

                popef_file_dumps[str(file)] = proc.stdout

            cls.__update_payload(popef_file_dumps, "popef_file_dumps")

            time.sleep(cls._POLLING_SECONDS)

    @classmethod
    def __get_weights(cls) -> str:
        """Get weights file paths and sizes from wherever possible."""

        # Search for all weight files and poll size/name
        weight_files = []
        weights_extensions = ["onnx", "pt", "pb"]
        cache_dirs = [
            ipynbname.path().parents[1],  # Local
            os.getenv("CHECKPOINT_DIR"),  # HF default
            os.getenv("HUGGINGFACE_HUB_CACHE"),  # Another possible HF path?
            os.getenv("TRANSFORMERS_CACHE"),  # Possible checkpoints here
        ]

        while True:
            if cls._LOG_STATE == "disabled":
                return

            for dir_path in cache_dirs:
                if dir_path:
                    for ext in weights_extensions:
                        weight_files.extend(Path(dir_path).glob(f"**/*.{ext}"))

            weight_file_sizes = {}
            for file in weight_files:
                weight_file_sizes[str(file)] = file.stat().st_size

            cls.__update_payload(json.dumps(weight_file_sizes), "weight_file_sizes")

            time.sleep(cls._POLLING_SECONDS)

    @classmethod
    def __get_datasets(cls) -> str:
        """Get dataset paths and sizes from wherever possible"""

        # Get all possible dataset dirs
        datasets = []
        dataset_dirs = [
            ipynbname.path().parents[1],  # Local
            os.getenv("HF_DATASETS_CACHE"),  # HF default
            os.getenv("PUBLIC_DATASETS_DIR"),  # Our default
            os.getenv("DATASETS_DIR"),  # /tmp/ location
        ]

        while True:
            if cls._LOG_STATE == "disabled":
                return

            for data_path in dataset_dirs:
                datasets.extend(list(Path(data_path).iterdir()))

            # Find sizes
            dataset_sizes = ""
            for folder in datasets:
                proc = subprocess.run(
                    ["du", "-sh", str(folder)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    shell=True,
                    text=True,
                )

                dataset_sizes = str(proc.stdout).split("\t")[0]

            cls.__update_payload(dataset_sizes, "dataset_sizes")

            time.sleep(cls._POLLING_SECONDS)

    @classmethod
    def __get_notebook_progression(cls) -> str:
        """Track cell exeuction order via timestamps

        Note: We use a custom IPython extension to track events, and use it to
        run some lines before any cell is executed. To avoid any noticeable
        delay, we keep this as light as possible, just recording the timestamp
        and cell input code.

        We write this to a cache file in .ipython/extensions/ and then append
        it to our main storage in this loop, flushing the cache afterwards.
        """

        while True:
            if cls._LOG_STATE == "disabled":
                return

            # Load cache files written by CellTracker extension
            cache_path = Path("/root/.ipython/extensions/cell_logs/").resolve()
            cache_files = cache_path.glob("**/*.json")

            # Read and combine all cell execution logs into one
            cell_executions = {}
            for file in cache_files:
                with open(file, "r") as f:
                    code = json.load(f)

                cell_executions[code["timestamp"]] = code

            # Delete all cached files
            # Subprocess since paperspace env dosent like unlink/remove
            for file in cache_files:
                subprocess.run(f"rm -rf {file}", shell=True)

            cls.__update_payload(cell_executions, "cell_executions")

            time.sleep(cls._POLLING_SECONDS)

    @classmethod
    def __get_errors(cls) -> str:
        """Log all errors and the code that produced them.

        Note: We use a custom IPython extension to track events, and use it to
        run some lines before any cell is executed. To avoid any noticeable
        delay, we keep this as light as possible, just recording the timestamp,
        cell input code and error.

        We write this to a cache file in .ipython/extensions/ and then append
        it to our main storage in this loop, flushing the cache afterwards.
        """

        while True:
            if cls._LOG_STATE == "disabled":
                return

            # Load cache files written by CellTracker extension
            cache_path = Path("/root/.ipython/extensions/cell_logs/errors").resolve()
            cache_files = cache_path.glob("**/*.json")

            # Read and combine all cell execution logs into one
            error_traces = {}
            for file in cache_files:
                with open(file, "r") as f:
                    error = json.load(f)

                error_traces[error["timestamp"]] = error

            # Delete all cached files
            # Subprocess since paperspace env dosent like unlink/remove
            for file in cache_files:
                subprocess.run(f"rm -rf {file}", shell=True)

            cls.__update_payload(error_traces, "error_traces")

            time.sleep(cls._POLLING_SECONDS)

    @classmethod
    def __get_first_error(cls):
        """Get the first ever error and what time it occured"""

        first_error_time = {}
        creation_time_obj = datetime.strptime(cls._CREATION_TIME, "%Y-%m-%dT%H:%M:%S.%fZ")

        while True:
            if cls._LOG_STATE == "disabled":
                return

            # Load cache files written by CellTracker extension
            cache_path = Path("/root/.ipython/extensions/cell_logs/errors").resolve()
            cache_files = cache_path.glob("**/*.json")

            # Record first ever error in the notebook
            if next(cache_files, None) is None and first_error_time is {}:
                cls._first_error_time = datetime.now()
                first_error_time["time_to_first_notebook_error"] = (
                    cls._first_error_time - creation_time_obj
                ).total_seconds()

            cls.__update_payload(first_error_time, "time_to_first_notebook_error")

            time.sleep(cls._POLLING_SECONDS)

    @classmethod
    def __get_compile_times(cls):
        """Capture compile time from noteboook.py

        Note: Because of how general this task is, it seems the best we can do
        for now is capture all output that mentions 'compilation' etc. and sift
        through the outputs later.

        If we can get more specificity on how compilation happens, what we can
        expect etc. (HF only, model.compile() explicit calls etc.) then we can
        clean this up a lot and be more particular about what we collect.
        """

        while True:
            if cls._LOG_STATE == "disabled":
                return

            with open(ipynbname.path()) as notebook:
                raw_notebook = nbformat.read(notebook, nbformat.NO_CONVERT)

            # Get all code cells, search for compile time
            code_cells = [
                (cell["source"], cell["outputs"]) for cell in raw_notebook["cells"] if cell["cell_type"] == "code"
            ]

            compilation_times = {}
            for input, output in code_cells:
                # Some cells have a seperate 'data' outputs. We need 'text' output
                if len(output) > 1:
                    output = output[1]

                if output:
                    try:
                        text = output[0].get("text")

                        # Assuming HF optimum pipeline output
                        # Check NoneType first else substring search throws
                        if text is not None and "Graph compilation: 100%" in text:
                            compilation_times[input] = text

                    # Suppress all outputs and continue
                    except:
                        pass

            cls.__update_payload({"compilation_times": json.dumps(compilation_times)}, "compilation_times")

            time.sleep(cls._POLLING_SECONDS)

    @classmethod
    def start_logging(cls):
        if cls._LOG_STATE == "ENABLED":
            print("GCLogger is already logging")
            return

        cls._LOG_STATE = "ENABLED"

        # Convert data collection into repeated polling with update checking
        background_functions = [
            cls.__get_notebook_metadata,
            cls.__get_frameworks_versions,
            cls.__get_executables,
            cls.__get_weights,
            cls.__get_datasets,
            cls.__get_notebook_progression,
            cls.__get_errors,
            cls.__get_first_error,
            cls.__get_compile_times,
            cls.__firehose_put,
        ]

        # Prepare shared dict and populate with Nulls in schema format
        with open(Path(__file__).parent.joinpath("columns.txt"), "r") as columns_file:
            columns = columns_file.read().split("\n")
        for col in columns:
            cls._PAYLOAD[col] = ""
            cls._OUTPUT_BUFFER[col] = ""

        # Start multiprocess procs for all functions
        cls._PROC_LIST = [mp.Process(target=func) for func in background_functions]
        for proc in cls._PROC_LIST:
            proc.daemon = True
            proc.start()

    @classmethod
    def stop_logging(cls):
        if cls._LOG_STATE == "DISABLED":
            print("GCLogger has already stopped logging")
            return

        if cls._LOG_STATE is None:
            print("GCLogger has not logged anything yet")
            return

        cls._LOG_STATE = "DISABLED"

        # Kill logging processes
        for proc in cls._PROC_LIST:
            proc.terminate()
            proc.join()

        print("GCLogger has stopped logging")


GCLogger()
