#!/bin/bash
# Sets root, python, scons, ssh, and batch environment for uscms servers

# Setup root environment using the shared CMSSW installation for EL9
. /cvmfs/cms.cern.ch/cmsset_default.sh
export SCRAM_ARCH=el9_amd64_gcc12
cd /cvmfs/cms.cern.ch/el9_amd64_gcc12/cms/cmssw/CMSSW_14_2_2/src
eval `scramv1 runtime -sh`
cd -

# path to scons for python 3.9
export PATH=./lib/python3.9/site-packages/bin:$PATH
export PYTHON3PATH=./lib/python3.9/site-packages/:$PYTHON3PATH

# Do multi-core scons
export SCONSFLAGS="-j $(nproc --all)"
export SET_ENV_PATH=set_env_uscms.sh # environment to use for build

# Change python to be in unbuffer mode for scripts to run commands
export PYTHONUNBUFFERED=1

# Prevent asking password using x11-gui
unset SSH_ASKPASS

# Setup environment for batch submission
source $(dirname $(readlink -e "$BASH_SOURCE"))/modules/jb_utils/set_env.sh
source $(dirname $(readlink -e "$BASH_SOURCE"))/modules/queue_system/set_env.sh
