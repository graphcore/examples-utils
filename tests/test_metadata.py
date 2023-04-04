# Copyright (c) 2023 Graphcore Ltd. All rights reserved.

import os
from examples_utils.paperspace_utils import create_metadata_file, get_metadata_file_data, check_files_match_metadata
import pytest
import shutil
import json
from pathlib import Path
import logging


def add_new_file(path: str, text: str):
    f = open(path, "a")
    f.write(text)
    f.close()


def delete_test_data():
    shutil.rmtree("test_metadata")


@pytest.fixture
def generate_data():
    # Delete any pre existing metadata test files
    if os.path.exists("test_metadata"):
        delete_test_data()
    # Create example dataset
    os.mkdir("test_metadata")
    add_new_file("test_metadata/test_metadata.txt", "Testing metadata file.")


@pytest.fixture
def generate_gradient_metadata_file():
    get_metadata_file_data("test_metadata")


def change_metadata_to_false_data():
    # Add a new file
    f = open("test_metadata/test_metadata_extra_file.txt", "a")
    f.write("Testing metadata recognises extra file.")
    f.close()
    # Load metadata file
    data = json.loads(Path("test_metadata/gradient_dataset_metadata.json").read_text())
    # Change file information in metadata
    data["files"][0]["size"] = 100
    # Add a new file in metadata that does not exist locally
    new_file_dict = dict(path="non existant file")
    data["files"] = data["files"] + [new_file_dict]
    create_metadata_file(data, Path("test_metadata"))


def test_metadata_checker(generate_data, generate_gradient_metadata_file, caplog):
    with caplog.at_level(logging.INFO):
        check_files_match_metadata("test_metadata", True)
    assert "All files in metadata found for test_metadata" in caplog.text

    with caplog.at_level(logging.INFO):
        change_metadata_to_false_data()
        check_files_match_metadata("test_metadata", True)
    assert "Extra files found in local storage: ['/test_metadata_extra_file.txt']" in caplog.text
    assert "files in metadata.json but not found in local storage: ['non existant file']" in caplog.text
    assert "Key: size\n gradient_metadata.json value: 100\n Local value: 22" in caplog.text
