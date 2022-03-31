# Copyright (c) 2022 Graphcore Ltd. All rights reserved.
import os.path
from tempfile import NamedTemporaryFile

import pytest

from examples_utils.custom_ops.custom_ops_utils import load_custom_ops_lib, get_binary_path

from multiprocessing import Process


def create_cpp_file():
    """Create C++ file to compile. Create new one per test."""
    # Create empty temp C++ file to compile
    cpp_code = """
    // cppimport
    #include <pybind11/pybind11.h>

    namespace py = pybind11;

    int square(int x) {
        return x * x;
    }

    PYBIND11_MODULE(somecode, m) {
        m.def("square", &square);
    }
    /*
    <%
    setup_pybind11(cfg)
    %>
    */
    """
    file = NamedTemporaryFile(suffix='.cpp', mode='w')
    file.write(cpp_code)
    return file


def test_custom_ops():
    cpp_file = create_cpp_file()

    # Compile first time
    load_custom_ops_lib(cpp_file.name)

    binary_path = get_binary_path(cpp_file.name)
    assert os.path.exists(binary_path)
    assert not os.path.exists(binary_path + '.lock')

    # Compile again
    load_custom_ops_lib(cpp_file.name)


def test_custom_ops_many_processors():
    cpp_file = create_cpp_file()
    processes = [Process(target=load_custom_ops_lib, args=(cpp_file.name, )) for i in range(1000)]

    for p in processes:
        p.start()

    for p in processes:
        p.join()

    assert all(p.exitcode == 0 for p in processes)

    load_custom_ops_lib(cpp_file.name)

    binary_path = get_binary_path(cpp_file.name)
    assert os.path.exists(binary_path)
    assert not os.path.exists(binary_path + '.lock')
