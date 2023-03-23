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
import psutil
import subprocess
import time
import multiprocessing as mp


from datetime import datetime
from pathlib import Path


class GCLogger(object):
    _instance = None
    _CREATION_TIME = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    _GC_LOG_STATE = None
    _GC_LOG_PATH = Path("/notebooks").joinpath("gc_logs", f"{_CREATION_TIME}")

    _FAST_POLLING_SECONDS = 10
    _SLOW_POLLING_SECONDS = 60

    _proc_list = []

    _BUCKET_NAME = "paperspace-uploading-test-bucket"
    _FIREHOSE_STREAM_NAME = "GCLOGGER_STREAM"
    _FIREHOSE_CLIENT = boto3.client("firehose")

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GCLogger, cls).__new__(cls)

            if cls._GC_LOG_STATE is None:
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
                    f"You can view the information being collected at: {cls._GC_LOG_PATH}\n"
                    "=============================================================================================================================================\n"
                )

                cls._GC_LOG_PATH.mkdir(parents=True, exist_ok=True)

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
                cls._FIREHOSE_CLIENT.create_delivery_stream(
                    DeliveryStreamName=cls._FIREHOSE_STREAM_NAME, S3DestinationConfiguration={}  # TODO
                )

        return cls._instance

    @classmethod
    def _firehose_put(cls, data: dict):
        """Submit a PUT record request to the firehose stream."""

        cls._FIREHOSE_CLIENT.put_record(DeliveryStreamName=cls._FIREHOSE_STREAM_NAME, Record=data)

    @classmethod
    def __log_env_block(cls):

        if cls._GC_LOG_STATE == "DISABLED":
            return

        env_state = dict(copy.deepcopy(os.environ))
        cls._firehose_put(env_state)

    @classmethod
    def __log_sysperf_info(cls):
        if cls._GC_LOG_STATE == "DISABLED":
            return

        log_dict = {}

        # Record some constants (CPU count, freq, disk setup)
        log_dict["CPU_count"] = psutil.cpu_count()
        log_dict["CPU_stats"] = str(psutil.cpu_stats())
        log_dict["CPU_freq"] = str(psutil.cpu_freq())

        # Collect all output of lscpu
        proc = subprocess.run(
            "lscpu -J",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=True,
            text=True,
        )
        log_dict["lscpu_results"] = json.loads(proc.stdout)

        # Collect quick disk performance stats (Disk <-> Host) in background
        command = (
            "fio --name=random-write --ioengine=posixaio --rw=randwrite "
            "--bs=4k --size=1g --numjobs=1 --iodepth=1 --runtime=5 "
            "--time_based --end_fsync=1 --output-format=json+"
        )
        proc = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=True,
            text=True,
        )
        log_dict["fio_results"] = proc.stdout

        cls._firehose_put(log_dict)

        # Clean up files from profiling
        # Subprocess since paperspace env dosent like unlink/remove
        test_file = cls._GC_LOG_PATH.parent.joinpath("random-write.0.0")
        if test_file.exists():
            subprocess.run(f"rm -rf {test_file}", shell=True)

    @classmethod
    def __log_ipuperf_info(cls):
        if cls._GC_LOG_STATE == "DISABLED":
            return

        # Get information for each IPU available
        num_ipus = int(os.getenv("NUM_AVAILABLE_IPU", "0"))

        # Host <-> IPU sync latency
        hostsync_results = {}
        for i in range(num_ipus):
            proc = subprocess.run(
                f"gc-hostsynclatencytest -d {i} -j",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                shell=True,
                text=True,
            )
            hostsync_results[i] = json.loads(proc.stdout)
        cls._firehose_put(hostsync_results)

        # Host <-> IPU data transfer
        hosttraffic_results = {}
        for i in range(num_ipus):
            subprocess.run(
                f"gc-hosttraffictest -d {i} -j",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                shell=True,
                text=True,
            )
            hosttraffic_results[i] = json.loads(proc.stdout)
        cls._firehose_put(hosttraffic_results)

        # IPU <-> IPU data transfer
        subprocess.run(
            "gc-iputraffictest --all-links -j",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=True,
            text=True,
        )
        iputraffic_results = json.loads(proc.stdout)
        cls._firehose_put(iputraffic_results)

    @classmethod
    def __log_notebook_info(cls):
        if cls._GC_LOG_STATE == "DISABLED":
            return

        notebook_metadata = {
            "notebook_path": str(ipynbname.path()),
            "repo_id": os.getenv("PAPERSPACE_NOTEBOOK_REPO_ID"),
            "cluster_id": os.getenv("PAPERSPACE_CLUSTER_ID"),
            "notebook_id": os.getenv("PAPERSPACE_NOTEBOOK_ID"),
            "jupyter_token": os.getenv("JUPYTER_TOKEN"),
            "paperspace_fqdn": os.getenv("PAPERSPACE_FQDN"),
            "paperspace_cluster_id": os.getenv("PAPERSPACE_CLUSTER_ID"),
            "paperspace_metric_workload_id": os.getenv("PAPERSPACE_METRIC_WORKLOAD_ID"),
        }
        cls._firehose_put(notebook_metadata)

        # Query pip packages and versions
        python_pkgs_versions = {i.key: i.version for i in pkg_resources.working_set}
        cls._firehose_put(python_pkgs_versions)

        # VIPU server information
        vipu_info = {
            "vipu_partition_id": os.getenv("IPUOF_VIPU_API_PARTITION_ID"),
            "hostname": os.getenv("HOSTNAME"),
            "num_ipus": os.getenv("NUM_AVAILABLE_IPU", "0"),
        }
        cls._firehose_put(vipu_info)

    @classmethod
    def __log_sysperf_metrics(cls):
        while True:
            if cls._GC_LOG_STATE == "DISABLED":
                return

            system_perf_metrics = {
                datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ"): {
                    "cpu_percent": psutil.cpu_percent(),
                    "virtual_memory": psutil.virtual_memory().percent,
                    "swap_memory": psutil.swap_memory().percent,
                    "disk_used": psutil.disk_usage("/").used,
                }
            }
            cls._firehose_put(system_perf_metrics)

            time.sleep(cls._FAST_POLLING_SECONDS)

    @classmethod
    def __get_executables(cls):
        cache_dirs = [
            ipynbname.path().parents[1],  # Local
            os.getenv("POPLAR_EXECUTABLE_CACHE_DIR"),  # HF default
            os.getenv("POPTORCH_CACHE_DIR"),  # Possible for non-HF optimum runs
        ]
        popef_files = []

        # Get all .popef files name and size
        for dir_path in cache_dirs:
            if dir_path:
                popef_files.extend(Path(dir_path).glob("*.popef"))

        popef_file_dumps = {}
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

        cls._firehose_put(popef_file_dumps)

    @classmethod
    def __get_weights(cls):
        cache_dirs = [
            ipynbname.path().parents[1],  # Local
            os.getenv("CHECKPOINT_DIR"),  # HF default
            os.getenv("HUGGINGFACE_HUB_CACHE"),  # Another possible HF path?
            os.getenv("TRANSFORMERS_CACHE"),  # Possible checkpoints here
        ]

        # Search for all weight files and poll size/name
        weights_extensions = ["onnx", "pt", "pb"]
        weight_files = []
        for dir_path in cache_dirs:
            if dir_path:
                for ext in weights_extensions:
                    weight_files.extend(Path(dir_path).glob(f"**/*.{ext}"))

        weight_file_sizes = {}
        for file in weight_files:
            weight_file_sizes[str(file)] = file.stat().st_size

        cls._firehose_put(weight_file_sizes)

    @classmethod
    def __get_datasets(cls):
        dataset_dirs = [
            ipynbname.path().parents[1],  # Local
            os.getenv("HF_DATASETS_CACHE"),  # HF default
            os.getenv("PUBLIC_DATASET_DIR"),  # Our default
            os.getenv("DATASET_DIR"),  # /tmp/ location
        ]

        # Get all possible dataset dirs
        datasets = []
        for data_path in dataset_dirs:
            datasets.extend(list(Path(data_path).iterdir()))

        # Find sizes
        dataset_sizes = {}
        for folder in datasets:
            proc = subprocess.run(
                ["du", "-sh", str(folder)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                shell=True,
                text=True,
            )

            dataset_sizes[str(folder)] = str(proc.stdout).split("\t")[0]

        cls._firehose_put(dataset_sizes)

    @classmethod
    def __log_file_metrics(cls):
        while True:
            if cls._GC_LOG_STATE == "DISABLED":
                return

            # Get possible .popef files
            cls.__get_executables()

            # Get possible weights and checkpoints files
            cls.__get_weights()

            # Get all datasets and sizes available
            cls.__get_datasets()

            time.sleep(cls._SLOW_POLLING_SECONDS)

    @classmethod
    def __log_notebook_progression(cls):
        """Track cell exeuction order via timestamps

        Note: We use a custom IPython extension to track events, and use it to
        run some lines before any cell is executed. To avoid any noticeable
        delay, we keep this as light as possible, just recording the timestamp
        and cell input code.

        We write this to a cache file in .ipython/extensions/ and then append
        it to our main storage in this loop, flushing the cache afterwards.
        """

        while True:
            if cls._GC_LOG_STATE == "DISABLED":
                return

            # Load cache files written by CellTracker extension
            cache_path = Path("/root/.ipython/extensions/cell_logs/").resolve()
            cache_files = cache_path.glob("**/*.json")

            # Read and combine all cell execution logs into one
            cell_execution_code = {}
            for file in cache_files:
                with open(file, "r") as f:
                    code = json.load(f)

                cell_execution_code[code["timestamp"]] = code

            cls._firehose_put(cell_execution_code)

            # Delete all cached files
            # Subprocess since paperspace env dosent like unlink/remove
            for file in cache_files:
                subprocess.run(f"rm -rf {file}", shell=True)

            time.sleep(cls._FAST_POLLING_SECONDS)

    @classmethod
    def __log_errors(cls):
        """Log all errors and the code that produced them.

        Note: We use a custom IPython extension to track events, and use it to
        run some lines before any cell is executed. To avoid any noticeable
        delay, we keep this as light as possible, just recording the timestamp,
        cell input code and error.

        We write this to a cache file in .ipython/extensions/ and then append
        it to our main storage in this loop, flushing the cache afterwards.
        """

        cls._first_error_time = None

        while True:
            if cls._GC_LOG_STATE == "DISABLED":
                return

            # Load cache files written by CellTracker extension
            cache_path = Path("/root/.ipython/extensions/cell_logs/errors").resolve()
            cache_files = cache_path.glob("**/*.json")

            # Record first ever error in the notebook
            if next(cache_files, None) is None and cls._first_error_time is None:
                cls._first_error_time = datetime.now()

            # Read and combine all cell execution logs into one
            error_traces = {}
            for file in cache_files:
                with open(file, "r") as f:
                    error = json.load(f)

                error_traces[error["timestamp"]] = error

            cls._firehose_put(error_traces)

            # Delete all cached files
            # Subprocess since paperspace env dosent like unlink/remove
            for file in cache_files:
                subprocess.run(f"rm -rf {file}", shell=True)

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

            with open(ipynbname.path()) as notebook:
                raw_notebook = nbformat.read(notebook, nbformat.NO_CONVERT)

            # Get all code cells, search for compile time
            code_cell_outputs = [cell["outputs"] for cell in raw_notebook["cells"] if cell["cell_type"] == "code"]

            compilation_statements = {}
            for output in code_cell_outputs:
                # Some cells have a seperate 'data' outputs. We need 'text' output
                if len(output) > 1:
                    output = output[1]

                if output:
                    try:
                        text = output[0].get("text")

                        # Assuming HF optimum pipeline output
                        # Check NoneType first else substring search throws
                        if text is not None and "Graph compilation: 100%" in text:
                            compilation_statements[datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ")] = text

                    # Suppress all outputs and continue
                    except:
                        pass

            cls._firehose_put(compilation_statements)

            time.sleep(cls._SLOW_POLLING_SECONDS)

    @classmethod
    def __log_session_stats(cls):
        """Record how long a user is in this session for and when they fail."""

        creation_time_obj = datetime.strptime(cls._CREATION_TIME, "%Y-%m-%dT%H:%M:%S.%fZ")

        while True:
            if cls._GC_LOG_STATE == "DISABLED":
                return

            timings = {}

            timings["session_time"] = str((datetime.now() - creation_time_obj).total_seconds())

            # Poll class attr to find first error
            if cls._first_error_time is not None:
                timings["first_error_time"] = cls._first_error_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                timings["time_until_error"] = (cls._first_error_time - creation_time_obj).total_seconds()

            cls._firehose_put(timings)

            time.sleep(cls._FAST_POLLING_SECONDS)

    @classmethod
    def start_logging(cls):
        if cls._GC_LOG_STATE == "ENABLED":
            print("GCLogger is already logging")
            return

        cls._GC_LOG_STATE = "ENABLED"

        background_functions = [
            # One-time collection
            # (constant, static information on system/env)
            cls.__log_env_block,
            cls.__log_sysperf_info,
            cls.__log_ipuperf_info,
            cls.__log_notebook_info,
            # Frequent polling every cls._FAST_POLLING_SECONDS
            # (changing values, metrics, measurements on system/env)
            cls.__log_sysperf_metrics,
            cls.__log_notebook_progression,
            cls.__log_errors,
            cls.__log_session_stats,
            # Infrequent polling every cls._SLOW_POLLING_SECONDS
            # (names, file sizes, packages etc.)
            cls.__log_file_metrics,
            cls.__log_compile_times,
        ]

        # Start multiprocess procs for all functions
        cls._proc_list = [mp.Process(target=func) for func in background_functions]

        for proc in cls._proc_list:
            proc.daemon = True
            proc.start()

    @classmethod
    def stop_logging(cls):
        if cls._GC_LOG_STATE == "DISABLED":
            print("GCLogger has already stopped logging")
            return

        if cls._GC_LOG_STATE is None:
            print("GCLogger has not logged anything yet")
            return

        cls._GC_LOG_STATE = "DISABLED"

        # Kill logging processes
        for proc in cls._proc_list:
            proc.terminate()
            proc.join()

        print("GCLogger has stopped logging")


GCLogger()
