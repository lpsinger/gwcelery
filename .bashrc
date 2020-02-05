# .bash_profile for deployment on LSC DataGrid clusters.
# Run at the start of an interactive shell (including a login shell).

# Source global definitions.
if [ -f /etc/bashrc ]; then
    . /etc/bashrc
fi

source /cvmfs/oasis.opensciencegrid.org/ligo/sw/conda/etc/profile.d/conda.sh
conda activate igwn-py37

# Add user site directory to the PATH. On Linux, this is usuall ~/.local/bin.
export PATH="$(python -m site --user-base)/bin${PATH+:${PATH}}"

# `pip install` should always behave as if it was called with `--user`.
export PIP_USER=1

# Disable OpenMP threading by default.
# In this environmnet, it will be enabled selectively by processes that use it.
export OMP_NUM_THREADS=1

# Use mpich for parameter estimation.
module load mpi/mpich-3.0-x86_64

# Unless the user has set `GSSAPIDelegateCredentials no` in their ~/.ssh/config
# file, their Globus certificate will be copied in when they log in, shadowing
# the robot certificate. Set these environment variables to override.
#
# Note: according to SSH_CONFIG(5), the default for `GSSAPIDelegateCredentials`
# is `no`. That's obviously incorrect!
export X509_USER_CERT="$HOME/.globus/usercert.pem"
export X509_USER_KEY="$HOME/.globus/userkey.pem"

# Configuration for GWCelery web applications.
export FLASK_PORT=5556
export FLASK_URL_PREFIX=/gwcelery
export FLOWER_PORT=5555
export FLOWER_URL_PREFIX=/flower

# GWCelery configuration-dependent instance variables.
case "${USER}" in
emfollow)
    export CELERY_CONFIG_MODULE="gwcelery.conf.production"
    ;;
emfollow-playground)
    export CELERY_CONFIG_MODULE="gwcelery.conf.playground"
    ;;
emfollow-test)
    export CELERY_CONFIG_MODULE="gwcelery.conf.test"
    ;;
esac
