# Copyright (c) 2019 Graphcore Ltd. All rights reserved.

import argparse
import datetime
import fileinput
import os
import re
import sys
import configparser
import json
import logging
from pathlib import Path

C_FILE_EXTS = [".c", ".cpp", ".cxx", ".c++", ".h", ".hpp"]

EXT_TO_COMMENT = {".py": "#", **{ext: "//" for ext in C_FILE_EXTS}}


def check_file(path: Path, amend: bool) -> bool:
    logging.debug(f"Checking: {path}")

    if path.stat().st_size == 0:
        # Empty file
        return True

    comment = EXT_TO_COMMENT[path.suffix.lower()]
    found_copyright = False
    first_line_index = 0
    line = "\n"
    with open(path, "r") as f:
        regexp = r"({} )*Copyright \(c\) \d+ Graphcore Ltd. All (r|R)ights (r|R)eserved.".format(comment)

        # Skip blank, comments and shebang
        while (
            line == "\n"
            or line.startswith('"""')
            or line.startswith("'''")
            or line.startswith(comment)
            or line.startswith("#!")
        ) and not re.match(regexp, line):
            if line.startswith("#!"):
                first_line_index += 1
            line = f.readline()

        # Check first line after skips
        if re.match(regexp, line):
            found_copyright = True

    if not found_copyright:
        if amend:
            now = datetime.datetime.now()
            year = now.year
            copyright_msg = "{} Copyright (c) {} Graphcore Ltd. All rights reserved.\n\n".format(comment, year)
            index = 0
            for line in fileinput.FileInput(path, inplace=True):
                if index == first_line_index:
                    line = copyright_msg + line
                print(line[:-1])
                index += 1

        logging.debug(f"File fails: {path}")
        return False

    logging.debug(f"File passes: {path}")
    return True


def read_git_submodule_paths():
    try:
        config = configparser.ConfigParser()
        config.read(".gitmodules")
        module_paths = [Path(config[k]["path"]).absolute() for k in config.sections()]
        if len(module_paths):
            print(f"Git submodule paths: {module_paths}")
        return module_paths
    except:
        print(f"No Git submodules found to exclude.")
        return []


def test_copyrights(paths, amend=False, exclude_json=None):
    """A test to ensure that every source file has the correct Copyright"""
    # Get all files based on the paths argument
    files = set()
    for path in paths:
        path = Path(path).absolute()

        if path.is_dir():
            files.update(list(path.rglob("*")))
        else:
            files.add(path)

    # Remove all files that are part of git submodules
    git_submodule_paths = read_git_submodule_paths()
    logging.info(f"Git submodule paths to exclude: {git_submodule_paths}")
    for git_submodule_path in git_submodule_paths:
        for file in list(files):
            if git_submodule_path in file.parents:
                files.discard(file)

    # Remove all files specified in exclude_json
    if exclude_json is not None:
        with open(exclude_json) as f:
            exclude_paths = json.load(f)["exclude"]
        logging.debug(f"Exclude file list: {exclude_paths}")
        for exclude_path in exclude_paths:
            files.discard(Path(exclude_path).absolute())

    # Remove all files generated by CMake, venv files and unsupported extension
    for file in list(files):
        is_cmake_file = "CMakeFiles" in file.parts
        is_venv_file = "venv" in file.parts
        is_unsupported_extention = file.suffix.lower() not in EXT_TO_COMMENT
        if is_cmake_file or is_venv_file or is_unsupported_extention:
            files.discard(file)

    logging.debug(f"Files to check: {files}")
    logging.info(f"Number of files to check: {len(files)}")

    # Check remaining files
    bad_files = []
    for file in files:
        if not check_file(file, amend):
            bad_files.append(file)

    if len(bad_files) > 0:
        sys.stderr.write("ERROR: The following files do not have " "copyright notices:\n\n")
        for f in bad_files:
            sys.stderr.write("    {}\n".format(f))
        raise RuntimeError(f"{len(bad_files)} files do not have copyright notices: {bad_files}")
    else:
        print("Copyright headers checks passed.")


def copyright_argparser(parser: argparse.ArgumentParser):
    """Add load lib build CLI commands to argparse parser"""
    parser.add_argument(
        "path",
        nargs="*",
        default=".",
        help="Path(s) to check or directory to search for files. "
        "Defaults to current working directory. You can also specify file(s) if you would like to check specific file(s).",
    )
    parser.add_argument("--amend", action="store_true", help="Amend copyright headers in files.")
    parser.add_argument(
        "--exclude-json",
        default=None,
        help="Provide a path to a JSON file which include files to exclude. "
        "The paths should be relative to the current working directory.",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        type=str,
        default="WARNING",
        help=("Loging level for the app. "),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Copyright header test")
    copyright_argparser(parser)
    opts = parser.parse_args()

    logging.basicConfig(
        level=opts.log_level, format="%(asctime)s %(levelname)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    logging.info(f"Staring. Process id: {os.getpid()}")

    try:
        test_copyrights(opts.path, opts.amend, opts.exclude_json)
    except AssertionError:
        sys.exit(1)
