import nbformat
from nbconvert.preprocessors import ExecutePreprocessor


def run_notebook(notebook_filename, cwd):
    """helper to run notebooks which may or may not be expected to fail"""
    with open(notebook_filename) as f:
        nb = nbformat.read(f, as_version=4)
    ep = ExecutePreprocessor(timeout=600, kernel_name="python3")
    ep.preprocess(nb, {"metadata": {"path": f"{cwd}"}})
