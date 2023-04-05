# Copyright (c) 2023 Graphcore Ltd. All rights reserved.

import os
from examples_utils.paperspace_utils import create_metadata_file, get_metadata_file_data, check_files_match_metadata
import pytest
import shutil
import json
from pathlib import Path
import logging


def delete_test_data():
    shutil.rmtree("test_metadata")


@pytest.fixture
def generate_data(tmp_path):
    # Create example dataset
    os.mkdir(tmp_path / "test_metadata")
    Path(tmp_path / "test_metadata/test_metadata.txt").write_text("Testing metadata file.")
    get_metadata_file_data("test_metadata", tmp_path)
    return tmp_path / "test_metadata"


def test_accurate_metadata(generate_data, caplog):
    print(generate_data)
    with caplog.at_level(logging.INFO):
        check_files_match_metadata(generate_data, True)
    assert "All files in metadata found for" in caplog.text


def test_extra_file_in_metadata(generate_data, caplog):
    with caplog.at_level(logging.INFO):
        data = json.loads(Path(generate_data / "gradient_dataset_metadata.json").read_text())
        # Add a new file in metadata that does not exist locally
        new_file_dict = dict(path="non existant file")
        data["files"] = data["files"] + [new_file_dict]
        create_metadata_file(data, generate_data)
        check_files_match_metadata(generate_data, True)
    assert "files in metadata.json but not found in local storage: ['non existant file']" in caplog.text


def test_extra_file_locally(generate_data, caplog):
    with caplog.at_level(logging.INFO):
        Path(generate_data / "test_metadata_extra_file.txt").write_text("Testing metadata recognises extra file.")
        check_files_match_metadata(generate_data, True)
    assert "Extra files found in local storage: ['/test_metadata_extra_file.txt']" in caplog.text


def test_file_size_inaccurate_in_metadata(generate_data, caplog):
    with caplog.at_level(logging.INFO):
        data = json.loads(Path(generate_data / "gradient_dataset_metadata.json").read_text())
        # Change file information in metadata
        data["files"][0]["size"] = 100
        create_metadata_file(data, generate_data)
        check_files_match_metadata(generate_data, True)
    assert "Key: size\n gradient_metadata.json value: 100\n Local value: 22" in caplog.text
