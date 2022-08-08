#!/bin/bash

# Default inputs
SDK_PATH="~/sdks/"
APPLICATION_NAME=$1
BENCHMARK=$2
BUILD_STEPS=$3
# Only for Pytorch cnns for now, the one exception
ADDITIONAL_DIR=$4

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

# Determine framework used
FRAMEWORK=${BENCHMARK_NAME:0:3}
if [[ $FRAMEWORK == "pyt" ]]
then
    FRAMEWORK="pytorch"
fi

# Install the framework-specific wheels
cd SDK_PATH
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
cd -

# Install application requirementsx
cd ~/examples/*/$APP_NAME/$FRAMEWORK/$ADDITIONAL_DIR/
pip3 install -r requirements.txt

# Run additional build steps
eval " $BUILD_STEPS"

# Run benchmark
python3 -m examples-utils --spec ./$ADDITIONAL_DIR/benchmarks.yml --benchmark $BENCHMARK --logdir ./tmp/${APP_NAME}_logs/

# Deactivate venv and disable sdk
deactivate
rm -rf ~/$APPLICATION
popsdk-clean
