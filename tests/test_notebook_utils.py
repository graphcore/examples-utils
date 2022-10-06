from pathlib import Path
import sys
import subprocess

from examples_utils.benchmarks import notebook_utils

TEST_DIRECTORY = Path(__file__).resolve().parent


def test_notebook_runner_captures_outputs():
    notebook_path = TEST_DIRECTORY / "test_files/sample.ipynb"
    std_streams, _ = notebook_utils.run_notebook(notebook_path, notebook_path.parent)
    assert "Notebook was run" in std_streams
    assert isinstance(std_streams, str)


def test_cli_equivalence():
    notebook_path = TEST_DIRECTORY / "test_files/sample.ipynb"
    cli_out = subprocess.check_output([sys.executable, "-m", "examples_utils.benchmarks.notebook_utils", str(notebook_path), str(notebook_path.parent)])
    std_streams, _ = notebook_utils.run_notebook(notebook_path, notebook_path.parent)

    # There are slightly different newlines from the cli and the function
    assert std_streams.strip() == cli_out.decode().strip()


if __name__ == "__main__":
    test_notebook_runner_captures_outputs()