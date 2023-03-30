# Copyright (c) 2023 Graphcore Ltd. All rights reserved.
"""
Checks if files in local folder match what is expected from the gradient_dataset_metadata.json

To use import the check_files_match_metadata function:
check_files_match_metadata(dataset_folder: str, compare_hash: bool)
"""

from typing import NamedTuple, Optional, List
from pathlib import Path
import os
import hashlib
import json
import logging


METADATA_FILENAME = "gradient_dataset_metadata.json"


def md5_hash_file(file_path: Path):
    md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        data = f.read()
        md5.update(data)
    return md5.hexdigest()


class GradientFileArgument(NamedTuple):
    """Arguments for uploading a file to Paperspace using the gradient API"""

    full_path: Path
    target_path: str

    @classmethod
    def from_filepath_and_dataset_path(cls, file_path: Path, dataset_path: Path):
        file_path = file_path.resolve()
        # Target path resolution needs to be an absolute folder starting with /
        target_path = file_path.resolve().parent.relative_to(dataset_path.resolve()).as_posix()
        target_path = "/" + str(target_path).lstrip(".")
        return cls(file_path, target_path)


def get_files_metadata(gradient_file_arguments: List[GradientFileArgument], generate_hash: bool):
    files_metadata = []
    for file_path, target_path in gradient_file_arguments:
        file_stat = os.stat(file_path)
        if target_path[-1] != "/":
            target_path += "/"
        path = target_path + file_path.name
        file_metadata = {"path": path, "size": file_stat.st_size}
        if generate_hash:
            file_metadata["md5_hash"] = md5_hash_file(file_path)
        files_metadata.append(file_metadata)
    return files_metadata


def preprocess_list_of_files(dataset_folder: Path, file_list: List[Path]) -> List[GradientFileArgument]:
    gradient_file_arguments: List[GradientFileArgument] = []
    for file_path in file_list:
        if file_path.is_file():
            gradient_file_arguments.append(
                GradientFileArgument.from_filepath_and_dataset_path(file_path, dataset_folder)
            )
    return gradient_file_arguments


def compare_file_lists(loaded_metadata_files: list, generated_locally_metadata_files: list):
    # Find extra or missing files and print an error, if so remove them from relevant lists
    expected_filepaths = list(map(lambda file_dict: file_dict["path"], loaded_metadata_files))
    local_filepaths = list(map(lambda file_dict: file_dict["path"], generated_locally_metadata_files))
    # Files found but not expected
    extra_files = [filepath for filepath in local_filepaths if filepath not in expected_filepaths]
    if extra_files:
        logging.warning("Extra files found in local storage: " + str(extra_files))
    # Files expected but not found
    missing_files = [filepath for filepath in expected_filepaths if filepath not in local_filepaths]
    if missing_files:
        logging.error("Missing files, files in metadata.json but not found in local storage: " + str(missing_files))
    # For all files left check that the keys are the same
    found_files_metadata = [filedict for filedict in loaded_metadata_files if filedict["path"] not in missing_files]
    found_files_locally = [
        filedict for filedict in generated_locally_metadata_files if filedict["path"] not in extra_files
    ]
    keys = generated_locally_metadata_files[0].keys()
    for i in range(len(found_files_metadata)):
        for key in keys:
            if found_files_locally[i][key] != found_files_metadata[i][key]:
                logging.warning(
                    "Difference in file found and file expected\n"
                    + "Path: "
                    + found_files_metadata[i]["path"]
                    + "\n"
                    + " Key: "
                    + key
                    + "\n"
                    + " gradient_metadata.json value: "
                    + str(found_files_metadata[i][key])
                    + "\n"
                    + " Local value: "
                    + str(found_files_locally[i][key])
                    + "\n"
                )


def check_files_match_metadata(dataset_folder: str, compare_hash: bool):
    dataset_folder = Path(dataset_folder)
    file_list = sorted(list(f for f in dataset_folder.rglob("*") if f.is_file() and f.name != METADATA_FILENAME))
    gradient_file_arguments = preprocess_list_of_files(dataset_folder, file_list)

    file_metadata = get_files_metadata(gradient_file_arguments, compare_hash)

    data = json.loads((dataset_folder / METADATA_FILENAME).read_text())

    compare_file_lists(data["files"], file_metadata)


def create_metadata_file(dictionary: dict, path: Path) -> str:
    content = json.dumps(dictionary, indent=4)
    file_name = path / METADATA_FILENAME
    with open(file_name, "w") as outfile:
        outfile.write(content)
    return file_name


def get_metadata_file_data(name: str):
    """Given the path to a folder, upload to a Gradient dataset of the same name
    using the gradient CLI."""
    dataset_folder = Path(os.getcwd()) / name

    starting_dir = Path.cwd()
    os.chdir(dataset_folder.parent)
    os.environ["PAPERSPACE_CLI_DEBUG"] = "true"
    dataset = Dataset.from_name(dataset_folder.name)
    version_id = f"{dataset.id}:{dataset.version}"
    logfile = f"log-upload-{dataset.name}-{version_id}.log"
    failed_log = f"uploads-{dataset.name}-{version_id}-failed.txt"
    complete_log = f"uploads-{dataset.name}-{version_id}-complete.txt"
    fileHandler = logging.FileHandler(logfile)
    logFormatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    fileHandler.setFormatter(logFormatter)
    logging.getLogger().addHandler(fileHandler)

    logging.info(f"Logging to file {Path.cwd() / logfile}, failures logged in {failed_log}")
    logging.info(f"Uploading {dataset.name} to {version_id}")
    file_list = sorted(list(f for f in dataset_folder.rglob("*") if f.is_file() and f.name != METADATA_FILENAME))
    Path(complete_log).write_text("\n".join(str(f) for f in file_list))
    gradient_file_arguments = preprocess_list_of_files(dataset_folder, dataset, logfile, failed_log, file_list)

    file_metadata = get_files_metadata(gradient_file_arguments)
    metadata = {"dataset": dataset._asdict(), "timestamp": str(datetime.datetime.now()), "files": file_metadata}

    metadata_filepath = create_metadata_file(metadata, dataset_folder)


# check_files_match_metadata("/home/evaw/evaw/workspace/gpj-release/gptj-6b-checkpoints", True)
