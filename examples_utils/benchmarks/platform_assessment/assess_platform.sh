#!/bin/bash

# Default inputs
SDK_PATH="~/sdks/"
APPLICATION_NAME=$1
BENCHMARK=$2
BUILD_STEPS=$3

# Enable SDK (poplar and popart)
cd SDK_PATH/poplar-*
source enable.sh
cd -

cd SDK_PATH/popart-*
source enable.sh
cd -

# Create and activate venv
# Assuming a compatible version of python is already available
apt-get install python3-virtualenv
python3 -m venv ~/$APPLICATION
source ~/$APPLICATION/bin/activate

# Upgrade pip
pip3 install --upgrade pip

# Install the framework-specific wheels
cd SDK_PATH
pip3 install 

# Determine framework used
FRAMEWORK=${BENCHMARK_NAME:0:3}
if [[ $FRAMEWORK == "pyt" ]]
then
    FRAMEWORK="pytorch"
fi

# Install application requirementsx
if [[ $FRAMEWORK == "pytorch" ]]
then
    pip3 install poptorch*
elif [[ $FRAMEWORK == "tf1" ]]
then
    pip3 install tensorflow-1*amd*
    pip3 install ipu_tensorflow_addons-1*
elif [[ $FRAMEWORK == "tf2" ]]
then
    pip3 install tensorflow-2*amd*
    pip3 install ipu_tensorflow_addons-2*
    pip3 install keras-2*
fi

pip3 install horovod*

# Run additional build steps
eval " $BUILD_STEPS"

# Run benchmark
python3 -m examples-utils --spec ~/examples/*/$APP_NAME/$FRAMEWORK/benchmark --benchmark $BENCHMARK --logdir ./${APP_NAME}_logs/

# Deactivate venv and disable sdk
deactivate
rm -rf ~/$APPLICATION
popsdk-clean
