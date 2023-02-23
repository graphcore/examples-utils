# Copyright (c) 2022 Graphcore Ltd. All rights reserved.

import os, sys
from enum import Enum
import pathlib
import json
import hashlib
import time
from uuid import getnode as get_mac
import git


class LoggingState(Enum):
    ENABLED = "ENABLED"
    DISABLED = "DISABLED"

    def __str__(self):
        return self.value


class LoggingTarget(Enum):
    LOCAL = "LOCAL"

    def __str__(self):
        return self.value


class ConfigLogger(object):
    _instance = None
    GC_EXAMPLE_LOG_CFG_PATH = pathlib.Path.home().joinpath(".graphcore", "command_logging")
    GC_EXAMPLE_LOG_CFG_FILE = GC_EXAMPLE_LOG_CFG_PATH.joinpath("config.json")
    GC_EXAMPLE_LOG_FILE = GC_EXAMPLE_LOG_CFG_PATH.joinpath("logs", f"{time.strftime('%Y_%m_%d')}.json")
    GC_EXAMPLE_LOG_STATE = None
    GC_EXAMPLE_LOG_TARGET = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigLogger, cls).__new__(cls)

            if "GC_EXAMPLE_LOG_TARGET" in os.environ:
                # TODO: later set collection interface based on this value
                try:
                    cls.GC_EXAMPLE_LOG_TARGET = LoggingTarget(os.environ["GC_EXAMPLE_LOG_TARGET"].upper())
                except Exception as e:
                    sys.stderr.write(f"Error: no known logging target type {os.environ['GC_EXAMPLE_LOG_TARGET']}")
                    cls.GC_EXAMPLE_LOG_STATE = LoggingState.DISABLED
                    return cls._instance
                if cls.GC_EXAMPLE_LOG_CFG_FILE.is_file():
                    try:
                        with open(cls.GC_EXAMPLE_LOG_CFG_FILE, "r") as f:
                            config = json.load(f)
                        cls.GC_EXAMPLE_LOG_STATE = LoggingState[config["GC_EXAMPLE_LOG_STATE"].upper()]
                    except Exception as e:
                        sys.stderr.write(
                            f"Error reading logging config file at {cls.GC_EXAMPLE_LOG_CFG_FILE.absolute()}. Error: {e}"
                        )
                        cls.GC_EXAMPLE_LOG_STATE = LoggingState.DISABLED
                else:
                    # request user and save their preferred choice
                    message = (
                        "\n\n====================================================================================================================================================\n\n"
                        "Graphcore would like to collect information about which examples and configurations have been run to improve usability and support for future users.\n\n"
                        "The information will be anonymised and logged locally to a file in `~/.graphcore` to be collected by your cloud provider.\n\n"
                        "You can disable this in the future by setting the environment variable GC_EXAMPLE_LOG_STATE to 'DISABLE' in a config file at `~/.graphcore/command_logging/config.json`.\n\n"
                        "Unless logging is disabled, the following information will be collected about the commands you run ONLY in Graphcore repositories:\n"
                        "\t- Timestamp of when the command was run\n"
                        "\t- Username of the user that ran the command (hashed for anonymity)\n"
                        "\t- The names of the Graphcore files run in the command\n"
                        "\t- The names of the Graphcore respositories contatining above files\n"
                        "\t- The Graphcore example application that was run\n"
                        "\t- The arguments passed in the command\n"
                        "====================================================================================================================================================\n\n"
                    )

                    print(message)

                    config_dict = {"GC_EXAMPLE_LOG_STATE": str(LoggingState.ENABLED)}
                    try:
                        cls.GC_EXAMPLE_LOG_CFG_PATH.mkdir(parents=True, exist_ok=True)
                        with open(cls.GC_EXAMPLE_LOG_CFG_FILE, "w") as f:
                            json.dump(config_dict, f)
                    except Exception as e:
                        sys.stderr.write(f"Error creating cloud logging config file. Error: {e}")

        return cls._instance

    @classmethod
    def log_example_config_dict(cls, log_dict):
        if not cls.GC_EXAMPLE_LOG_TARGET or cls.GC_EXAMPLE_LOG_STATE == LoggingState.DISABLED:
            return

        if cls.GC_EXAMPLE_LOG_TARGET == LoggingTarget.LOCAL:
            try:
                if not cls.GC_EXAMPLE_LOG_FILE.is_file():
                    cls.GC_EXAMPLE_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
                    with open(cls.GC_EXAMPLE_LOG_FILE, "w") as f:
                        json.dump({"log": []}, f)

                with open(cls.GC_EXAMPLE_LOG_FILE, "r+") as f:
                    conf = json.load(f)
                    conf["log"].append(log_dict)
                    f.seek(0)
                    json.dump(conf, f)
            except Exception as e:
                sys.stderr.write(f"Config logging error logging to file: {e}")
        else:
            sys.stderr.write(f"Config logging target not supported {cls.GC_EXAMPLE_LOG_TARGET}")

    @classmethod
    def log_example_config_run(cls):
        if not cls.GC_EXAMPLE_LOG_TARGET or cls.GC_EXAMPLE_LOG_STATE == LoggingState.DISABLED:
            return

        log_dict = {}

        log_dict["timestamp"] = time.time()

        # to anonymise the username, hash the mac address concatenated with the username
        # (because a mac address is not as easily knowable) TODO: this doesn't make much sense.. could use a public key instead maybe?
        h = hashlib.sha256()
        username = os.environ.get("USER")
        mac_address = get_mac()
        unique_user_hash = f"{mac_address}_{username}"
        h.update(unique_user_hash.encode("utf-8"))

        log_dict["userhash"] = h.hexdigest()[:10]

        # get path to script
        script_path = pathlib.Path().joinpath(sys.argv[0]).absolute()
        script_name = script_path.name
        log_dict["script_name"] = script_name

        # get path of repo from absolute script path
        git_repo = git.Repo(script_path, search_parent_directories=True)
        repo_path = pathlib.Path(git_repo.git.rev_parse("--show-toplevel"))

        repo_name = repo_path.name
        log_dict["repository"] = repo_name

        example_path = script_path.parent.relative_to(repo_path)
        log_dict["example"] = str(example_path)

        command_args = sys.argv[1:]
        log_dict["command_args"] = command_args

        cls.log_example_config_dict(log_dict=log_dict)


ConfigLogger()
