# Copyright (c) 2023 Graphcore Ltd. All rights reserved.
from datetime import datetime
from genericpath import isdir
from posixpath import expandvars
import subprocess
import json
import os
import yaml
import logging
from metadata_utils import check_files_match_metadata
from pathlib import Path
from string import Template


def check_files_exist(files: [str], dirname: str):
    dirpath = Path(dirname)
    if not dirpath.exists():
        logging.warning("Directory " + dirname + " doesnot exist")
        return
    else:
        logging.info("Directory " + dirname + " exists")
    sub_directories = [str(f) for f in dirpath.iterdir() if f.is_dir()]
    for filename in files:
        full_path = str(dirpath / filename)
        if full_path not in sub_directories:
            logging.warning(filename + " not found in " + dirname)
        else:
            dataset_sub_directories = [str(f) for f in Path(full_path).iterdir()]
            if full_path + "/gradient_dataset_metadata.json" in dataset_sub_directories:
                logging.info("Metadata found in " + full_path)
                check_files_match_metadata(full_path, False)
            else:
                logging.warning("Metadata file not found in " + full_path)


def check_paths_exists(paths: [str]):
    for path in paths:
        if Path(path).exists():
            logging.info("Folder exists: " + path)
        else:
            logging.warning("Folder does not exist " + path)


# Check that the number of detected IPUs is correct
# Ideally this should get the number of IPUs from the host names
def check_num_pod_expected(logger: logging.Logger):
    pod_type = os.getenv("GRAPHCORE_POD_TYPE")
    expected_ipu_num = pod_type.replace("pod", "")

    num_ipus = os.getenv("NUM_AVAILABLE_IPU", "0")

    if expected_ipu_num != num_ipus:
        logger.warning("Incorrect number of IPUs found " + num_ipus + " expected " + expected_ipu_num)
    else:
        logger.info("Correct number IPUs found")


def expand_env_variables(path: str):
    path = os.path.expandvars(path)
    return path


def expand_env_variables_error_thrown(path: str):
    path = Template(path).substitute(os.environ)
    return path


def main():
    notebook_id = os.environ.get("PAPERSPACE_METRIC_WORKLOAD_ID", "")
    # Check that graphcore_health_checks folder exists
    if not os.path.isdir("./storage/graphcore_health_checks"):
        os.makedirs("./storage/graphcore_health_checks")

    logging.basicConfig(
        filename="./storage/graphcore_health_checks/" + str(datetime.now()) + "_" + notebook_id + ".json",
        format="%(message)s",
        filemode="w",
    )

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    logging.info("Running health check")
    logging.info("Checking datasets mounted")
    # Check that the datasets have mounted as expected

    # Gather the datasets expected from the settings.yaml
    with open("settings.yaml") as f:
        my_dict = yaml.safe_load(f)
        datasets = my_dict["integrations"].keys()

    # Check that dataset exists and if a metadata file is found check that all files in the metadata file exist
    check_files_exist(datasets, "./datasets")

    # Check that the folders specified in the key of the symlink_config.json exist
    logging.info("Checking symlink folders exist")
    with open("symlink_config.json") as f:
        symlinks = json.load(f)
        new_folders = list(map(expand_env_variables, symlinks.keys()))
    check_paths_exists(new_folders)


if __name__ == "__main__":
    main()
