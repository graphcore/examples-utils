# Copyright (c) 2023 Graphcore Ltd. All rights reserved.

import subprocess

from pathlib import Path
from .gc_logger import *

# Help IPython find our custom extension
extension_path = Path(__file__).parent.joinpath("cell_logger.py").resolve()
destination_path = Path("/root/.ipython/extensions").resolve()

subprocess.run(f"cp {extension_path} {destination_path}", shell=True)
