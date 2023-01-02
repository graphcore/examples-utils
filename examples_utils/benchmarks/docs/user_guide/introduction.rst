Introduction
------------

Poplar™ is a graph-programming framework for the Graphcore Intelligence
Processing Unit (IPU), a new type of processor aimed at artificial intelligence
and machine learning applications. An overview of the IPU architecture and
programming model can be found in the `IPU Programmer's Guide
<https://docs.graphcore.ai/projects/ipu-programmers-guide/>`_.
You should familiarize yourself with this document before reading this guide.

The Poplar SDK includes tools and libraries to support programming the IPU. The Poplar SDK libraries provide a C++ interface. Poplar also supports industry-standard machine learning frameworks such as TensorFlow, MXNET, ONNX, Keras, and PyTorch which can be accessed from Python.

There are a number of example programs included with the SDK in the ``examples``
directory of the Poplar installation. Further examples, tutorials and
benchmarks are available on the `Graphcore GitHub
<https://github.com/graphcore>`_.

The Poplar library provides classes and functions to implement and deploy parallel programs on the IPU. It uses a graph-based method to describe programs and, although it can be used to describe arbitrary accelerated computation, it has been designed specifically to suit the needs of artificial intelligence and machine learning applications.

The PopLibs libraries are a set of application libraries that implement operations commonly required by machine learning applications, such as linear algebra operations, elementwise tensor operations, non-linearities and reductions. These provide a fast and easy way to create programs that run efficiently using the parallelism of the IPU.

There are several command line tools to manage the IPU hardware. These are
described in the "Getting Started" guide for your IPU system and the
`IPU Command Line Tools <https://docs.graphcore.ai/projects/command-line-tools/>`_
document.
