# Copyright (c) 2022 Graphcore Ltd. All rights reserved.

import os
import cppimport.import_hook
from . import sdk_version_hash_lib

__all__ = ['sdk_version_hash']

import random


def sdk_version_hash() -> str:
    """Graphcore SDK version hash (sanitised output from C++ function `poplar::packageHash`)"""
    rand = str(random.random())
    print('called sdk_version_hash', rand)
    return str(random.random())
    if not os.environ.get('EXAMPLES_UTILS_SDK_VERSION_HASH_TEST'):
        return sdk_version_hash_lib.sdk_version_hash()
    else:
        # For testing purposes
        print('IM HERE')
        return os.environ['EXAMPLES_UTILS_SDK_VERSION_HASH_TEST']
