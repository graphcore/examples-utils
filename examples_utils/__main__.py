# Copyright (c) 2022 Graphcore Ltd. All rights reserved.

import argparse
import sys

from examples_utils.benchmarks.environment_utils import preprocess_args
from examples_utils.benchmarks.run_benchmarks import benchmarks_parser, run_benchmarks
from examples_utils.benchmarks.logging_utils import configure_logger
from examples_utils.load_lib_utils.cli import load_lib_build_parser, load_lib_builder_run
from examples_utils.testing.test_copyright import copyright_argparser, test_copyrights


def main(raw_args):
    parser = argparse.ArgumentParser()

    subparsers = parser.add_subparsers(dest='subparser')

    load_lib_build_subparser = subparsers.add_parser(
        'load_lib_build', description='Use load_lib to build all eligible files in specified directory.')
    load_lib_build_parser(load_lib_build_subparser)

    benchmarks_subparser = subparsers.add_parser('benchmark', description="Run examples benchmarks")
    benchmarks_parser(benchmarks_subparser)

    copyright_subparser = subparsers.add_parser('test_copyright', description="Run copyright header test.")
    copyright_argparser(copyright_subparser)

    args = parser.parse_args(raw_args[1:])

    if len(raw_args) <= 1:
        parser.print_usage()
        sys.exit(1)

    if args.subparser == 'load_lib_build':
        load_lib_builder_run(args)
    elif args.subparser == 'benchmark':
        args = preprocess_args(args)
        configure_logger(args)
        run_benchmarks(args)
    elif args.subparser == 'test_copyright':
        test_copyrights(args.path, args.amend, args.exclude_json)
    else:
        err = ("Please select form one of:\n\t`load_lib_build`\n\t`benchmark`\n\t`test_copyright`")
        raise Exception(err)


if __name__ == "__main__":
    main(sys.argv)
