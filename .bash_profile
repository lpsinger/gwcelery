# .bash_profile for deployment on LSC DataGrid clusters.
# Run at the start of a login shell.

. ~/.bashrc

# Warn the user to go through GitLab for normal deployment changes.
whiptail --yesno "The low-latency pipeline is continuously deployed through \
GitLab. Please use the GitLab interface to make any software updates or \
configuration changes or to start, stop, or restart the pipeline. For \
details, refer to:

https://gwcelery.readthedocs.io/en/latest/deployment.html

Interactive terminal sessions are for EMERGENCY USE ONLY. \
Are you sure that you want to proceed?" 15 70 --defaultno \
--title 'FOR EMERGENCY USE ONLY' --backtitle $(hostname --fqdn) || logout
