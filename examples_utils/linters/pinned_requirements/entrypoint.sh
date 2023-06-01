#!/bin/bash
python3 -m pip install -r utils/linters/pinned_requirements/requirements.txt
python3 -m utils.linters.pinned_requirements.pinned_requirements $@
exit $?
