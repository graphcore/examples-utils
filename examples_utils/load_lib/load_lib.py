# Copyright (c) 2022 Graphcore Ltd. All rights reserved.
import shutil
from time import sleep, time

import ctypes
from contextlib import suppress

from cppimport.checksum import is_checksum_valid
from cppimport.importer import get_module_name, get_extension_suffix, setup_module_data, template_and_build
from filelock import FileLock, Timeout

from examples_utils import sdk_version_hash
import os
import logging

__all__ = ['load_lib']


def get_module_data(filepath_custom_op: str):
    """Create module data dictionary that cppimport uses"""
    fullname = os.path.splitext(os.path.basename(filepath_custom_op))[0]
    return setup_module_data(fullname, filepath_custom_op)


def get_module_data_new_path(filepath_custom_op: str):
    module_data = get_module_data(filepath_custom_op)
    binary_path = get_binary_path(filepath_custom_op)
    module_data['ext_path'] = binary_path
    module_data['ext_name'] = os.path.basename(binary_path)
    return module_data


def get_binary_path(filepath_custom_op: str) -> str:
    """Binary path is cppimport binary path plus sdk version
    e.g.`opname.gc-sdk-5f7a58bf8e.cpython-36m-x86_64-linux-gnu.so`"""
    fullname = os.path.splitext(os.path.basename(filepath_custom_op))[0]
    file_name = get_module_name(fullname) + f'.gc-sdk-{sdk_version_hash()}' + get_extension_suffix()
    path = os.path.join(os.path.dirname(filepath_custom_op), file_name)
    return path


def load_lib(path_custom_op: str, timeout: int = 5 * 60):
    """Builds if necessary and loads the custom op binary.

    If the Graphcore SDK version has changed between compilations it automatically recompiles.

    Has safeguards against multiple processes trying to compile at the same time.

    Parameters:
        path_custom_op (str): path of the custom op C++ file
        timeout (int): timeout time if cannot obtain lock to compile

    Returns:
        binary_path: path to binary file
    """
    path_custom_op = os.path.abspath(path_custom_op)  # Build tools can have issues if relative path
    if not os.path.exists(path_custom_op):
        raise FileNotFoundError(f"Custom op file does not exist: {path_custom_op}")

    binary_path = get_binary_path(path_custom_op)
    lock_path = binary_path + '.lock'

    module_data = get_module_data(path_custom_op)
    module_data_new_path = get_module_data_new_path(path_custom_op)

    t = time()

    # Need to check:
    # 1) binary path exists - otherwise the binary could be compiled against a different SDK
    # 2) binary checksum - otherwise the c++ source may of changed and need to recompile
    while not (os.path.exists(binary_path) and is_checksum_valid(module_data_new_path)) and time() - t < timeout:
        try:
            with FileLock(lock_path, timeout=1):
                if os.path.exists(binary_path) and is_checksum_valid(module_data_new_path):
                    break
                template_and_build(path_custom_op, module_data)
                cppimport_binary_path = module_data['ext_path']
                shutil.copy(cppimport_binary_path, binary_path)
                os.remove(cppimport_binary_path)
                logging.debug(f'{os.getpid()}: Built binary')
        except Timeout:
            logging.debug(f'{os.getpid()}: Could not obtain lock')
            sleep(1)

    if not (os.path.exists(binary_path) and is_checksum_valid(module_data_new_path)):
        raise Exception(
            f'Could not compile binary as lock already taken and timed out. Lock file will be deleted: {lock_path}')

    if os.path.exists(lock_path):
        with suppress(OSError):
            os.remove(lock_path)

    lib = ctypes.cdll.LoadLibrary(binary_path)
    logging.debug(f'{os.getpid()}: Loaded binary')

    return lib
