# Copyright (c) 2022 Graphcore Ltd. All rights reserved.

import ctypes
import os
import logging
import cppimport
from cppimport.find import _check_first_line_contains_cppimport
from cppimport.importer import (
    build_safely,
    is_build_needed,
    setup_module_data,
)
import tempfile

__all__ = ['load_lib']

settings = {'file_exts': ('.cpp', )}


def _build(filepath, timeout: int = 5 * 60):
    """
    Code taken and modified from cppimport:
    https://github.com/tbenthompson/cppimport/blob/3d3de85c708effa9e27bbd32de1a48aac301d870/cppimport/__init__.py

    The MIT License (MIT)
    Copyright (c) 2021 T. Ben Thompson
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f'File does not exist: {filepath}')
    filepath = os.path.abspath(filepath)
    fullname = os.path.splitext(os.path.basename(filepath))[0]

    old_timeout = cppimport.settings.get('lock_timeout', 5 * 60)
    try:
        cppimport.settings['lock_timeout'] = timeout
        module_data = setup_module_data(fullname, filepath)
        if is_build_needed(module_data):
            build_safely(filepath, module_data)
        binary_path = module_data["ext_path"]
    finally:
        cppimport.settings['lock_timeout'] = old_timeout

    return binary_path


def get_module_data(filepath: str):
    """Create module data dictionary that `cppimport` uses"""
    fullname = os.path.splitext(os.path.basename(filepath))[0]
    return setup_module_data(fullname, filepath)


def load_lib(filepath: str, timeout: int = 5 * 60):
    """Compile a C++ source file using `cppimport`, load the shared library into the process using `ctypes` and
    return it.

    Compilation is only triggered if an existing binary does not match the source file hash. You can also use
    `depend_on_sdk_version` within the `cppimport` comment to trigger recompilation when the Graphcore SDK version
    changes.

    `cppimport` is used to compile the source which uses a special comment in the C++ file that includes the
    compilation parameters. Here is an example of such a comment which defines compiler flags, additional sources files
    and library options (see `cppimport` documentation for more info):

    ```
    /*
    <%
    cfg['sources'] = ['another_source.cpp']
    cfg['extra_compile_args'] = ['-std=c++14', '-fPIC', '-O2', '-DONNX_NAMESPACE=onnx', '-Wall']
    cfg['libraries'] = ['popart', 'poplar', 'popops', 'poputil', 'popnn']
    from examples_utils.load_lib_utils.load_lib_utils import depend_on_sdk_version
    depend_on_sdk_version(cfg)
    setup_pybind11(cfg)
    %>
    */
    ```

    Its also recommended to include the cppimport header at the top of the source file `\\ cppimport` to indicate that
    it will be loaded via cppimport and so the `load_lib_all` function will build it.

    Parameters:
        filepath (str): File path of the C++ source file
        timeout (int): Timeout time if cannot obtain lock to compile the source

    Returns:
        lib: library instance. Output of `ctypes.cdll.LoadLibrary`
    """

    binary_path = _build(filepath, timeout)
    lib = ctypes.cdll.LoadLibrary(binary_path)

    return lib


def load_lib_all(dir_path: str, timeout: int = 5 * 60, load: bool = True):
    """
    Recursively search the directory `dir_path` and use `load_lib` to build and load eligible files.

    Eligible files have a `cpp` file extension and the first line contains the comment `\\ cppimport`.

    Args:
        dir_path: Path of directory to start search for files to compile
        timeout: Timeout of `load_lib` compile
        load: If True will load the libs and return, otherwise just compile

    Returns:
        libs: If `load==True` return a list of tuples (path, lib) otherwise just a list of paths of compiled files
    """
    libs = []
    for directory, _, files in os.walk(dir_path):
        for file in files:
            if (not file.startswith(".") and os.path.splitext(file)[1] in settings["file_exts"]):
                full_path = os.path.join(directory, file)
                if _check_first_line_contains_cppimport(full_path):
                    logging.info(f'Building: {full_path}')
                    if load:
                        lib = load_lib(full_path, timeout)
                        libs += [(full_path, lib)]
                    else:
                        _build(full_path)
                        libs += [full_path]
                    logging.info(f'Built: {full_path}')
                else:
                    logging.info('Skipping source file as it does not contain `// cppimport` comment at the top: '
                                 f'{full_path}')

    return libs


def depend_on_sdk_version(cfg):
    """Add this within the cppimport comment in the C++ source file to ensure a rebuild is triggered when the SDK
    version changes"""
    from examples_utils.sdk_version_hash import sdk_version_hash
    _, tmp_path = tempfile.mkstemp(suffix='.h')
    with open(tmp_path, 'w') as f:
        f.write('// ' + sdk_version_hash())
    cfg['dependencies'].append(tmp_path)
