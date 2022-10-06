from pathlib import Path
from examples_utils.benchmarks import notebook_utils


TEST_DIRECTORY = Path(__file__).resolve().parent

def test_notebook_runner_captures_outputs():
    notebook_path = TEST_DIRECTORY / "test_files/sample.ipynb"
    stdstreams, _ = notebook_utils.run_notebook(notebook_path, notebook_path.parent)
    assert "Notebook was run" in stdstreams
    assert isinstance(stdstreams, str)


if __name__ == "__main__":
    test_notebook_runner_captures_outputs()