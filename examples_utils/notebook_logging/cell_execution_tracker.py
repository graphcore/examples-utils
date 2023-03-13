# Copyright (c) 2023 Graphcore Ltd. All rights reserved.

import ipynbname
import json
import nbformat
import os

from datetime import datetime
from IPython.core.magic import register_line_magic


class CellExecutionTracker(object):
    """Tracks the execution order of cells and outputs analyses."""

    def __init__(self, ip):
        self.shell = ip

    def pre_run_cell(self, info):
        print("execution_time:", datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ"))
        print(
            "input:",
        )


def load_ipython_extension(ip):
    tracker = CellExecutionTracker(ip)
    ip.events.register("pre_run_cell", tracker.pre_run_cell)
