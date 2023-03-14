# Copyright (c) 2023 Graphcore Ltd. All rights reserved.

import json
import sys

from datetime import datetime
from pathlib import Path


# class DevNull:
#     def write(self, msg):
#         pass


# sys.stdout = DevNull()
# sys.stderr = DevNull()


class CellLogger(object):
    """Tracks the times at which cells are executed"""

    def __init__(self, ip):
        self.shell = ip

        self.log_path = Path("/root/.ipython/extensions/cell_logs/").resolve()
        self.log_path.mkdir(parents=True, exist_ok=True)

    def pre_run_cell(self, info):
        """Runs just before any cell is run"""

        # TODO: Can we get cell ID? Perhaps output too?
        timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        code = info.raw_cell

        # Write to ipython cache to be sure
        try:
            cache_path = self.log_path.joinpath(f"{timestamp}.txt")

            with open(cache_path, "w") as outfile:
                outfile.write(code)

        # Silently skip if not possible
        except:
            pass


def load_ipython_extension(ip):
    tracker = CellLogger(ip)
    ip.events.register("pre_run_cell", tracker.pre_run_cell)
