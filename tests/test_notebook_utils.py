from pathlib import Path
import sys
import subprocess
import copy

import pytest

from examples_utils.benchmarks import notebook_utils
from examples_utils.benchmarks.run_benchmarks import process_notebook_to_command

TEST_DIRECTORY = Path(__file__).resolve().parent


def test_notebook_runner_captures_outputs():
    notebook_path = TEST_DIRECTORY / "test_files/sample.ipynb"
    std_streams = notebook_utils.run_notebook(notebook_path, notebook_path.parent)
    assert "Notebook was run" in std_streams
    assert isinstance(std_streams, str)


def test_cli_equivalence():
    notebook_path = TEST_DIRECTORY / "test_files/sample.ipynb"
    cli_out = subprocess.check_output([sys.executable, "-m", "examples_utils.benchmarks.notebook_utils", str(notebook_path), str(notebook_path.parent)])
    std_streams = notebook_utils.run_notebook(notebook_path, notebook_path.parent)

    # There are slightly different newlines from the cli and the function
    assert std_streams.strip() == cli_out.decode().strip()


class TestNotebook2Cmd:
    """Test that conversion from notebook to variant is as expected"""
    def test_no_op_if_not_there(self):
        variant = {"cmd": "poprun"}
        variant_out = process_notebook_to_command(copy.deepcopy(variant))
        for k, v in variant.items():
            assert variant_out[k] == v
        for k, v in variant_out.items():
            assert variant[k] == v

    def test_error_if_cmd_and_notebook(self):
        variant = {"cmd": "poprun", "notebook": None}
        with pytest.raises(ValueError, match="Invalid combination of entries"):
            process_notebook_to_command(variant)


    @pytest.mark.parametrize("variant_factory", [
        lambda file: {"notebook": {"file": file},},
        lambda file: {"notebook": {"file": file, "working_directory": file.parent},},
        lambda file: {"notebook": file,},
    ])
    def test_replaces_notebook(self, variant_factory):
        notebook_path = TEST_DIRECTORY / "test_files/sample.ipynb"
        variant = variant_factory(notebook_path)
        reference_out = notebook_utils.run_notebook(notebook_path, variant.get("working_directory", "."))
        variant = process_notebook_to_command(copy.deepcopy(variant))
        cli_out = subprocess.check_output(variant["cmd"].split(" "))
        assert reference_out.strip() == cli_out.decode().strip()

if __name__ == "__main__":
    test_notebook_runner_captures_outputs()