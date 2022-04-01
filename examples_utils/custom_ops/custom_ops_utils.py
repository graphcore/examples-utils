# Copyright (c) 2022 Graphcore Ltd. All rights reserved.

from time import sleep, time

from cppimport import build_filepath
import ctypes
import shutil
from contextlib import suppress
from filelock import FileLock

from examples_utils import sdk_version_hash
import os
import logging

__all__ = ['load_custom_ops_lib']


def get_binary_path(path_custom_op: str) -> str:
    return f'{path_custom_op}_{sdk_version_hash()}.so'


def load_custom_ops_lib(path_custom_op: str, timeout: int = 5 * 60):
    """Builds if necessary and loads the custom op binary.

    If the Graphcore SDK version has changed between compilations it automatically recompiles.

    Has safeguards against multiple processes trying to compile at the same time.

    Parameters:
        path_custom_op (str): path of the custom op C++ file
        timeout (int): timeout time if cannot obtain lock to compile

    Returns:
        binary_path: path to binary file
    """
    binary_path = get_binary_path(path_custom_op)
    lock_path = binary_path + '.lock'

    t = time()
    while not os.path.exists(binary_path) and time() - t < timeout:
        try:
            with FileLock(lock_path, timeout=1):
                if os.path.exists(binary_path):
                    break
                cppimport_binary_path = build_filepath(path_custom_op)
                shutil.copy(cppimport_binary_path, binary_path)
                os.remove(cppimport_binary_path)
                logging.debug(f'{os.getpid()}: Built binary')
        except FileExistsError:
            logging.debug(f'{os.getpid()}: Could not obtain lock')
            sleep(1)

    if not os.path.exists(binary_path):
        raise Exception(
            f'Could not compile binary as lock already taken and timed out. Trying to delete the lock: {lock_path}')

    if os.path.exists(lock_path):
        with suppress(OSError):
            os.remove(lock_path)

    lib = ctypes.cdll.LoadLibrary(binary_path)
    logging.debug(f'{os.getpid()}: Loaded binary')

    return lib
