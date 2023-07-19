# Copyright (c) 2023 Graphcore Ltd. All rights reserved.

import pytest
import shutil

from pathlib import Path
from typing import Dict, Generator, List, Tuple

from requirements.requirement import Requirement
from examples_utils.precommit.pinned_requirements.pinned_requirements import (
    main,
    manual_parse_named_git,
    is_valid_req,
    invalid_requirements,
    try_write_fixed_requirements,
)

TEST_FILE_ROOT = Path(__file__).parent / "test_files"


REQUIREMENTS: List[Tuple[str, bool]] = [
    ("protobuf==3.19.4", True),
    ("wandb>=0.12.8", False),
    ("horovod[pytorch]==0.24.0", True),
    ("git+https://github.com/graphcore/examples-utils@latest_stable", True),
    ("git+https://github.com/graphcore/examples-utils", False),
    ("cmake==3.22.4", True),
    ("numpy==1.23.5; python_version > '3.7'", True),
    ("numpy==1.19.5; python_version <= '3.7'", True),
    ("pandas", False),
    (
        "examples-utils[common] @ git+https://github.com/graphcore/examples-utils.git@7cd37a8eccabe88e3741eef2c31bafd4fcd30c4c",
        True,
    ),
    (
        "examples-utils @ git+https://github.com/graphcore/examples-utils.git",
        False,
    ),
    ("torch>=2.0.0+cpu", False),
    ("torch>=2.0.0+cpu # req: unpinned", True),
]


@pytest.mark.parametrize(
    "line, expected_result",
    [
        ("git+https://github.com/graphcore/examples-utils@latest_stable", True),
        ("git+https://github.com/graphcore/examples-utils", False),
        (
            "examples-utils[common] @ git+https://github.com/graphcore/examples-utils.git@7cd37a8eccabe88e3741eef2c31bafd4fcd30c4c",
            True,
        ),
        (
            "examples-utils @ git+https://github.com/graphcore/examples-utils.git",
            False,
        ),
    ],
)
def test_manual_parse_named_git(line: str, expected_result: bool):
    output = manual_parse_named_git(line)
    assert output == expected_result


@pytest.mark.parametrize("line, expected_result", REQUIREMENTS)
def test_is_valid_req(line: str, expected_result: bool):
    req = Requirement.parse(line)
    output = is_valid_req(req)
    assert output == expected_result


def create_req_file(tmp_path: Path, requirement_dict: Dict[str, bool]) -> str:
    req_file = tmp_path / "requirements.txt"
    with open(req_file, "w") as fh:
        for r in requirement_dict.keys():
            fh.write(r + "\n")

    return str(req_file)


def test_invalid_requirements(tmp_path: Path):
    requirement_dict = dict(REQUIREMENTS)
    req_file = create_req_file(tmp_path, requirement_dict)
    invalid = invalid_requirements(req_file, False)

    invalid_lines = [r.line for r in invalid]
    for req_line, valid in requirement_dict.items():
        if not valid:
            assert req_line in invalid_lines
        else:
            assert req_line not in invalid_lines


@pytest.mark.parametrize(
    "reqs, expected_result",
    [
        (REQUIREMENTS, 1),
        ([REQUIREMENTS[0]], 0),
    ],
)
def test_main(tmp_path: Path, reqs: List[Tuple[str, bool]], expected_result: int):
    requirement_dict = dict(reqs)
    req_file = create_req_file(tmp_path, requirement_dict)
    output = main([req_file], False)
    assert output == expected_result


def test_bad_filename():
    output = main(["myfile.txt"])
    assert output == 2


def check_output(output_val: int, expected_output: int, truth_fn: Path, actual_fn: Path):
    assert output_val == expected_output

    with open(truth_fn) as fh:
        expected_lines = fh.readlines()

    with open(actual_fn) as fh:
        changed_lines = fh.readlines()

    # assert len(expected_lines) == len(changed_lines)

    for e, c in zip(expected_lines, changed_lines):
        assert e == c


def test_fix_invalid(tmp_path: Path, mocker: Generator["MockerFixture", None, None]):
    mock_api = mocker.MagicMock(name="metadata")
    mock_api.side_effect = lambda x: "5.5.1" if x == "pyyaml" else None

    mocker.patch("importlib.metadata.version", new=mock_api)

    invalid = [
        Requirement.parse("pyyaml"),
        Requirement.parse("git+https://github.com/graphcore/examples-utils"),
    ]

    tmp_filepath = tmp_path / "requirements.txt"
    shutil.copyfile(TEST_FILE_ROOT / "mock_requirements.txt", tmp_filepath)

    output = try_write_fixed_requirements(invalid, tmp_filepath)

    assert output == True
    check_output(output, 1, TEST_FILE_ROOT / "expected_fixed_requirements.txt", tmp_filepath)


def test_fix_invalid_all_valid(tmp_path: Path):
    tmp_filepath = tmp_path / "requirements.txt"
    shutil.copyfile(TEST_FILE_ROOT / "expected_fixed_requirements.txt", tmp_filepath)
    output = try_write_fixed_requirements([], tmp_filepath)

    check_output(output, False, TEST_FILE_ROOT / "expected_fixed_requirements.txt", tmp_filepath)
