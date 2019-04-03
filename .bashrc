# .bash_profile for deployment on LSC DataGrid clusters.
# Run at the start of an interactive shell (including a login shell).

# Source global definitions.
if [ -f /etc/bashrc ]; then
    . /etc/bashrc
fi

# Set default Python runtime to 3.6.
source /opt/rh/rh-python36/enable

# Add user site directory to the PATH. On Linux, this is usuall ~/.local/bin.
export PATH="$(python -m site --user-base)/bin${PATH+:${PATH}}"

# `pip install` should always behave as if it was called with `--user`.
export PIP_USER=1

# Unless the user has set `GSSAPIDelegateCredentials no` in their ~/.ssh/config
# file, their Globus certificate will be copied in when they log in, shadowing
# the robot certificate. Set these environment variables to override.
#
# Note: according to SSH_CONFIG(5), the default for `GSSAPIDelegateCredentials`
# is `no`. That's obviously incorrect!
export X509_USER_CERT="$HOME/.globus/usercert.pem"
export X509_USER_KEY="$HOME/.globus/userkey.pem"

# GWCelery instance variables.
export CELERY_BROKER_URL="redis+socket://${HOME}/redis.sock"

# GWCelery configuration-dependent instance variables.
case "${USER}" in
emfollow)
    export CELERY_CONFIG_MODULE="gwcelery.conf.production"
    export FLOWER_PORT="5555"
    export FLASK_PORT="5556"
    export FLOWER_URL_PREFIX="/flower"
    export FLASK_URL_PREFIX="/gwcelery"
    ;;
emfollow-playground)
    export CELERY_CONFIG_MODULE="gwcelery.conf.playground"
    export FLOWER_PORT="5557"
    export FLASK_PORT="5558"
    export FLOWER_URL_PREFIX="/playground/flower"
    export FLASK_URL_PREFIX="/playground/gwcelery"
    ;;
esac
