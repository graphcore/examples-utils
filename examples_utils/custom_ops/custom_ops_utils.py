# Copyright (c) 2022 Graphcore Ltd. All rights reserved.

from time import sleep, time

from cppimport import build_filepath
import ctypes
import os
import shutil
import sys
from contextlib import contextmanager

from examples_utils import sdk_version_hash


@contextmanager
def open_and_delete(path, mode):
    """Open file and delete it on exit"""
    with open(path, mode) as f:
        yield f
    try:
        os.remove(path)
    except IOError:
        sys.stderr.write('Failed to clean up temp file {}'.format(path))


def load_custom_ops_lib(path_custom_op: str, timeout: int = 5 * 60) -> str:
    """Builds if necessary and loads the custom op binary.

    If the Graphcore SDK version has changed between compilations it automatically recompiles.

    Parameters:
        path_custom_op (str): path of the custom op C++ file
        timeout (int): timeout time if cannot obtain lock to compile

    Returns:
        binary_path: path to binary file
    """
    binary_path = f'{path_custom_op}_{sdk_version_hash()}.so'
    lock_path = binary_path + '.lock'

    t = time()
    while not os.path.exists(binary_path) and time() - t < timeout:
        try:
            with open_and_delete(lock_path, 'x') as compile_lock:
                cppimport_binary_path = build_filepath(path_custom_op)
                shutil.copy(cppimport_binary_path, binary_path)
                os.remove(cppimport_binary_path)
        except FileExistsError:
            sleep(1)

    if not os.path.exists(binary_path):
        raise Exception(
            f'Could not compile binary as lock already taken and timed out. Try deleting the lock: {lock_path}')

    ctypes.cdll.LoadLibrary(binary_path)

    return binary_path
