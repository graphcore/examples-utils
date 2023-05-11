# examples-utils
Utils and common code for Graphcore's example applications

## Command line interface (CLI)

The package includes some command line interface utils. For more details refer to the CLI help message:

```python
python -m examples_utils --help
```

## Installation

This package can be installed from source via pip:

```console
python -m pip install https://github.com/graphcore/examples-utils.git
```

By default it will only install a minimal set of requirements. To benchmark notebooks you must
install the "jupyter" set of requirements:

```console
python -m pip install https://github.com/graphcore/examples-utils.git[jupyter]
```

If you'd like to set the install to a fixed commit, then we reccommend using the [latest_stable](https://github.com/graphcore/examples-utils/releases/tag/latest_stable) tag, which is tested and updated frequently to maintain functionality. You can use this by adding: 

```console
examples-utils[common] @ git+https://github.com/graphcore/examples-utils@latest_stable
```
to your requirements.txt file

## Benchmarking

The benchmarking sub-package is used for running the benchmarks that are provided with example applications in the [examples](https://github.com/graphcore/examples) repository. For more information, refer to the [benchmark's README](https://github.com/graphcore/examples-utils/blob/master/examples_utils/benchmarks/README.md).

## GC Logger (notebook logging)

The Graphcore logger for notebooks is a module in the form of an IPython extension that tracks user behaviour within the Jupyter notebooks we provide via paperspace. For more information, refer to the [notebook logging README](https://github.com/graphcore/examples-utils/blob/master/examples_utils/notebook_logging/README.md)

## Development

* Reformat code to repo standard: `make lint`
* Use [Google style docstrings](https://sphinxcontrib-napoleon.readthedocs.io/en/latest/example_google.html)
* Do not push to master branch. Make changes through github PR requests.

## Licence

See file `LICENSE`