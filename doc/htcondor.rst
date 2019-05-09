.. highlight:: shell-session

Running under HTCondor
======================

The recommended way to start and stop GWCelery on the LIGO Data Grid cluster is
using HTCondor_. See the example HTCondor submit file `gwcelery.sub`_. This
submit file will start up Redis, the worker processes, the Flask web
application, and Flower. It will create some log files and a Unix domain
socket, so you should first navigate to a directory where you want these files
to go. For example::

    $ mkdir -p ~/gwcelery/var && cd ~/gwcelery/var

Then run the submit file as follows::

    $ gwcelery.sub
    Submitting job(s)........
    8 job(s) submitted to cluster 293497.

To stop GWCelery, run the ``condor_hold`` command::

    $ condor_hold -constraint 'JobBatchName == "gwcelery"'
    All jobs matching constraint (JobBatchName == "gwcelery") have been held

To restart GWCelery, run ``condor_release``::

    $ condor_release -constraint 'JobBatchName == "gwcelery"'
    All jobs matching constraint (JobBatchName == "gwcelery") have been released

Note that there is normally **no need** to re-submit GWCelery if the machine is
rebooted, because the jobs will persist in the HTCondor queue.


.. _HTCondor: https://research.cs.wisc.edu/htcondor/
.. _gwcelery.sub: https://git.ligo.org/emfollow/gwcelery/blob/master/gwcelery/data/gwcelery.sub

Shortcuts
---------

The following commands are provided as shortcuts for the above operations::

    $ gwcelery condor submit
    $ gwcelery condor rm
    $ gwcelery condor q
    $ gwcelery condor hold
    $ gwcelery condor release

The following command is a shortcut for
``gwcelery condor rm; gwcelery condor submit``::

    $ gwcelery condor resubmit

Managing multiple deployments
-----------------------------

There should generally be at most one full deployment of GWCelery per GraceDB
server running at one time. The ``gwcelery condor`` shortcut command is
designed to protect you from accidentally starting multiple deployments of
GWCelery by inspecting the HTCondor job queue before submitting new jobs. If
you try to start GWCelery a second time on the same host in the same directory,
you will get the following error message::

    $ gwcelery condor submit
    error: GWCelery jobs are already running in this directory.
    You must first remove exist jobs with "gwcelery condor rm".
    To see the status of those jobs, run "gwcelery condor q".

However, there are situations where you may actually want to run multiple
instances of GWCelery on the same machine. For example, you may want to run one
instance for the 'production' GraceDB server and one for the 'playground'
server. To accomplish this, just start the two instances of gwcelery in
different directories. Here is an example::

    $ mkdir -p production
    $ pushd production
    $ CELERY_CONFIG_MODULE=gwcelery.conf.production gwcelery condor submit
    $ popd
    $ mkdir -p playground
    $ pushd playground
    $ CELERY_CONFIG_MODULE=gwcelery.conf.playground gwcelery condor submit
    $ popd
