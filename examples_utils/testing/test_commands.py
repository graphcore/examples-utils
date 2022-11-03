# Copyright (c) 2022 Graphcore Ltd. All rights reserved.
from typing import Union, List
import subprocess
import warnings
import re

DEFAULT_PROCESS_TIMEOUT_SECONDS = 40 * 60


class CalledProcessError(subprocess.CalledProcessError):
    """An error for subprocesses which captures stdout and stderr in the error message."""

    def __str__(self) -> str:
        original_message = super().__str__()
        return f"{original_message}\n" f"{self.stdout}\n" f"{self.stderr}"


def check_missing_patterns(string: str, expected_patterns: List[str]):
    """Finds patterns which are not in a string.

    This function is used to search through the output of commands for
    specific expected patterns.

    Args:
        string: A string which needs to contain the given patterns.
        expected_patterns: regular expression patterns that are expected
            in the string.

    Returns:
        A list with the expected_patterns which were not matched.
    """
    if not expected_patterns:
        return
    # If a string is passed as an argument convert it to a list
    if isinstance(expected_patterns, str):
        expected_patterns = [expected_patterns]

    missing_matches = [
        expected for expected in expected_patterns if not re.search(expected, string)
    ]

    assert not missing_matches, (
            f"Not all strings were found in the output of the command, the "
            f"following expected strings were missing: {missing_matches}. "
            f"The following output was produced: {string}"
        )

def run_command_fail_explicitly(
    command: Union[str, List[str]],
    cwd: str = ".",
    *,
    suppress_warnings: bool = False,
    **kwargs,
) -> str:
    """Runs a command returning the output or failing with useful information

    Args:
        command: The command to execute, can also be a space separated string.
        cwd: The directory in which the command should be
            launched. If called by a pytest test function or method, this
            probably should be a `tmp_path` fixture.
        suppress_warnings: Do not include warnings in stdout, so it can be
                           parsed more reliably. Will still be captured if
                           command raises an exception.
        **kwargs: Additional keyword arguments are passed to
            `subprocess.check_output`.

    Returns:
        The standard output and error of the command if successfully executed.

    Raises:
        RuntimeError: If the subprocess command executes with a non-zero output.
    """

    if suppress_warnings:
        # Warn if parameters contradict
        if "stderr" in kwargs and kwargs["stderr"] != subprocess.PIPE:
            warnings.warn(
                "`run_command_fail_explicitly` parameter `suppress_warnings` will"
                " override other specified parameter `stderr`. Using"
                " `stderr=subprocess.PIPE`",
                stacklevel=2,
            )

        # PIPE rather None, so we can still access from exceptions below
        kwargs["stderr"] = subprocess.PIPE

    DEFAULT_KWARGS = {
        "shell": isinstance(command, str) and " " in command,
        "stderr": subprocess.STDOUT,
        "timeout": DEFAULT_PROCESS_TIMEOUT_SECONDS,
        "universal_newlines": True,
    }

    try:
        merged_kwargs = {**DEFAULT_KWARGS, **kwargs}
        out = subprocess.check_output(
            command,
            cwd=cwd,
            **merged_kwargs,
        )
    except subprocess.CalledProcessError as e:
        stdout = e.stdout
        stderr = e.stderr
        # type of the stdout stream will depend on the subprocess.
        # The python docs say decoding is to be handled at
        # application level.
        if hasattr(stdout, "decode"):
            stdout = stdout.decode("utf-8", errors="ignore")
        if hasattr(stderr, "decode"):
            stderr = stderr.decode("utf-8", errors="ignore")
        raise CalledProcessError(1, cmd=command, output=stdout, stderr=stderr) from e
    return out
