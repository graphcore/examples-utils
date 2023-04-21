# Copyright (c) 2023 Graphcore Ltd. All rights reserved.
from datetime import datetime
import json
import os
import yaml
import logging
from metadata_utils import check_files_match_metadata
from pathlib import Path
from string import Template
from time import time


def check_files_exist(files: [str], dirname: str):
    dirpath = Path(dirname)
    output_dict = {}
    if not dirpath.exists():
        logging.warning("Directory " + dirname + " doesnot exist")
        return {"warning": "Directory " + dirname + " doesnot exist"}
    else:
        logging.info("Directory " + dirname + " exists")
    sub_directories = [str(f) for f in dirpath.iterdir() if f.is_dir()]
    for filename in files:
        full_path = str(dirpath / filename)
        if full_path not in sub_directories:
            logging.warning(filename + " not found in " + dirname)
            output_dict[filename] = {
                "warning": filename + " dataset not mounted, " + filename + " directory not found in " + dirname
            }
        else:
            dataset_sub_directories = [str(f) for f in Path(full_path).iterdir()]
            if full_path + "/gradient_dataset_metadata.json" in dataset_sub_directories:
                logging.info("Metadata found in " + full_path)
                output_dict[filename] = check_files_match_metadata(full_path, False)
            else:
                logging.warning("Metadata file not found in " + full_path)
                output_dict[filename] = {"warning": "Metadata file not found in " + full_path}
    return output_dict


def check_paths_exists(paths: [str]):
    symlinks_exist = []
    for path in paths:
        if Path(path).exists():
            logging.info("Folder exists: " + path)
            symlinks_exist.append({path: True})
        else:
            logging.warning("Folder does not exist " + path)
            symlinks_exist.append({path: False})
    return symlinks_exist


def main():
    notebook_id = os.environ.get("PAPERSPACE_METRIC_WORKLOAD_ID", "")
    # Check that graphcore_health_checks folder exists
    if not os.path.isdir("/storage/graphcore_health_checks"):
        os.makedirs("/storage/graphcore_health_checks")

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
    datasets_mounted = check_files_exist(datasets, "/datasets")

    # Check that the folders specified in the key of the symlink_config.json exist
    logging.info("Checking symlink folders exist")
    with open("symlink_config.json") as f:
        symlinks = json.load(f)
        new_folders = list(map(os.path.expandvars, symlinks.keys()))
    symlinks_exist = check_paths_exists(new_folders)

    output_json_dict = {"mounted_datasets": datasets_mounted, "symlinks_exist": symlinks_exist}
    Path(
        "/storage/graphcore_health_checks/"
        + datetime.fromtimestamp(time()).strftime("%Y-%m-%d-%H.%M.%S")
        + "_"
        + notebook_id
        + ".json"
    ).write_text(json.dumps(output_json_dict, indent=4))


if __name__ == "__main__":
    main()
