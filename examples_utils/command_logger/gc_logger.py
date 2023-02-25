# Copyright (c) 2022 Graphcore Ltd. All rights reserved.

import json
import os
import pathlib
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
    GC_LOG_DELAY_SECONDS = 10

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
    def __write_dict_to_file(cls, log_dict, filename):
        if cls.GC_LOG_STATE == "DISABLED":
            return

        try:
            if not filename.is_file():
                filename.parent.mkdir(parents=True, exist_ok=True)
                with open(filename, "w") as f:
                    json.dump({"log": []}, f)

            with open(filename, "r+") as f:
                conf = json.load(f)
                conf["log"].append(log_dict)
                f.seek(0)
                json.dump(conf, f)
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
    def __log_sysperf_metrics(cls):
        if cls.GC_LOG_STATE == "DISABLED":
            return

        while True:
            # CPU utilisation
            cls.iteration_dict["cpu_percent"] = psutil.cpu_percent()

            # virtual/swap memory usage
            cls.iteration_dict["virtual_memory"] = psutil.virtual_memory().percent
            cls.iteration_dict["swap_memory"] = psutil.swap_memory().percent

            # Disk usage
            cls.iteration_dict["disk_used"] = psutil.disk_usage("/").used

            with open(cls.GC_LOG_CFG_PATH.joinpath("cpu_metrics.log"), "a") as outfile:
                json.dump(cls.iteration_dict, outfile)

            time.sleep(cls.GC_LOG_DELAY_SECONDS)

    @classmethod
    def __log_ipuperf_info(cls):
        if cls.GC_LOG_STATE == "DISABLED":
            return

        # Get information for each IPU available
        with open(cls.GC_LOG_CFG_PATH.joinpath("ipu_perf.log"), "a") as outfile:
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
    def start_logging(cls):
        if cls.GC_LOG_STATE == "DISABLED":
            return

        iteration_dict = {}

        cls.__log_sysperf_info(cls)

        cls.__log_sysperf_metrics(cls)

        cls.__log_ipuperf_info(cls)

        cls.log_dict[str(time.time())] = iteration_dict


GCLogger()
