# Copyright (c) 2022 Graphcore Ltd. All rights reserved.
import subprocess
from contextlib import contextmanager
from glob import glob
from tempfile import TemporaryDirectory
from unittest.mock import patch

import hashlib
from pathlib import Path

import cppimport
import pytest

import os
from multiprocessing import Process

from examples_utils import load_lib
from examples_utils.load_lib_utils.load_lib_utils import get_module_data, load_lib_all

cpp_code_no_pybind = """// cppimport

int square(int x) {
    return x * x;
}

/*
<%
from examples_utils.load_lib_utils.load_lib_utils import depend_on_sdk_version
depend_on_sdk_version(cfg)
%>
*/
"""


@contextmanager
def create_cpp_file(cpp_source=cpp_code_no_pybind):
    """Create C++ file to compile. Create new one per test."""
    # Create empty temp C++ file to compile

    with TemporaryDirectory() as tmp_dir:
        path = os.path.join(tmp_dir, 'module.cpp')
        with open(path, 'w') as f:
            f.write(cpp_source)
        yield path


def md5_file_hash(path: str) -> str:
    # File data + creation time + modified time
    data = Path(path).read_bytes() \
            + bytes(str(os.path.getctime(path)), 'utf8') \
            + bytes(str(os.path.getmtime(path)), 'utf8')
    return hashlib.md5(data).hexdigest()


def test_load_lib():
    with create_cpp_file() as cpp_file:
        module_data = get_module_data(cpp_file)
        binary_path = module_data['ext_path']

        # Compile first time
        load_lib(cpp_file)
        cppimport.build_filepath(cpp_file)
        assert os.path.exists(binary_path)
        binary_hash = md5_file_hash(binary_path)

        # Test loading again when already compiled (binary should be untouched)
        load_lib(cpp_file)

        assert binary_hash == md5_file_hash(binary_path)


def test_load_lib_file_change():
    with create_cpp_file() as cpp_file:
        module_data = get_module_data(cpp_file)
        binary_path = module_data['ext_path']

        # Compile first time
        load_lib(cpp_file)
        assert os.path.exists(binary_path)
        binary_hash = md5_file_hash(binary_path)

        # Test loading again when file has changed
        with open(cpp_file, 'a') as f:
            f.write('\n int x = 1;')

        load_lib(cpp_file)
        assert os.path.exists(binary_path)
        assert binary_hash != md5_file_hash(binary_path)


def test_load_lib_sdk_change():
    with create_cpp_file() as cpp_file:
        module_data = get_module_data(cpp_file)
        binary_path = module_data['ext_path']

        # Compile first time
        print('FIRST TIME')
        load_lib(cpp_file)
        assert os.path.exists(binary_path)
        binary_hash = md5_file_hash(binary_path)

        # Test loading again when sdk version has changed
        try:
            os.environ['EXAMPLES_UTILS_SDK_VERSION_HASH_TEST'] = 'patch-version'
            # # Check version patch
            # from examples_utils.sdk_version_hash import sdk_version_hash
            # assert 'patch-version' == sdk_version_hash(), 'Patch has not worked'

            # Compile again
            print('SECOND TIME')
            load_lib(cpp_file)
            assert os.path.exists(binary_path)
            assert binary_hash != md5_file_hash(binary_path)
        finally:
            del os.environ['EXAMPLES_UTILS_SDK_VERSION_HASH_TEST']


def test_load_lib_many_processors():
    with create_cpp_file() as cpp_file:
        processes = [Process(target=load_lib, args=(cpp_file, )) for i in range(1000)]

        for p in processes:
            p.start()

        for p in processes:
            p.join()

        assert all(p.exitcode == 0 for p in processes)

        load_lib(cpp_file)

        module_data = get_module_data(cpp_file)
        binary_path = module_data['ext_path']
        assert os.path.exists(binary_path)
        assert not os.path.exists(binary_path + '.lock')


@pytest.mark.parametrize('load', (True, False))
def test_load_lib_all(load):
    with TemporaryDirectory() as tmp_dir:
        tmp_dir = Path(tmp_dir)
        os.makedirs(Path(tmp_dir) / 'dir1' / 'dir2')

        # Write cpp 3 files in nested dirs
        with open(tmp_dir / 'module.cpp', 'w') as f:
            f.write(cpp_code_no_pybind)

        with open(Path(tmp_dir) / 'dir1' / 'module.cpp', 'w') as f:
            f.write(cpp_code_no_pybind)

        with open(Path(tmp_dir) / 'dir1' / 'dir2' / 'module.cpp', 'w') as f:
            f.write(cpp_code_no_pybind)

        # Decoy file
        with open(tmp_dir / 'module.not_cpp', 'w') as f:
            f.write(cpp_code_no_pybind)

        libs = load_lib_all(str(tmp_dir), load=load)
        assert len(libs) == 3


def test_cli():
    with create_cpp_file() as cpp_file:
        file_dir = os.path.dirname(cpp_file)
        output = subprocess.run(["python3", "-m", "examples_utils", 'load_lib_build', file_dir],
                                check=True,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        shell_output = str(output.stdout) + '\n' + str(output.stderr)
        binaries = glob(file_dir + '/*.so')
        assert 'Built' in shell_output
        assert len(binaries) > 0
