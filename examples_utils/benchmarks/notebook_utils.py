import os

import nbformat
from nbconvert.preprocessors import ExecutePreprocessor
from nbconvert import Exporter
from nbformat import NotebookNode
from nbconvert.exporters.exporter import ResourcesDict


def run_notebook(notebook_filename: str, working_directory: str) -> str:
    """Run a notebook and return all its outputs to stdstream together

    Args:
        notebook_filename: The path to the notebook file that needs testing
        working_directory: The working directory from which the notebook is
            to be run.
    """
    with open(notebook_filename) as f:
        nb = nbformat.read(f, as_version=4)
    ep = ExecutePreprocessor(timeout=600, kernel_name="python3")
    ep.preprocess(nb, {"metadata": {"path": f"{working_directory}"}})

    exporter = OutputExporter()
    output = exporter.from_notebook_node(nb)
    return output


class OutputExporter(Exporter):
    """nbconvert Exporter to export notebook output as single string source code."""

    # Extension of the file that should be written to disk (used by parent class)
    file_extension = ".py"

    def from_notebook_node(self, nb: NotebookNode, **kwargs):
        notebook, _ = super().from_notebook_node(nb, **kwargs)
        # notebooks are lists of cells, code cells are of the format:
        # {"cell_type": "code",
        #  "outputs":[
        #     {
        #         "output_type": "stream"|"bytes",
        #         "text":"text of interest that we want to capture"
        #     }, ...]}
        # Hence the following list comprehension:
        cell_outputs = [
            output.get("text", "") + os.linesep
            for cell in notebook.cells
            if cell.cell_type == "code"
            for output in cell.outputs
            if output
            if output.get("output_type") == "stream"
        ]

        outputs = os.linesep.join(cell_outputs)

        return outputs, ResourcesDict()
