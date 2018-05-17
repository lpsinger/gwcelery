# Running under HTCondor

The recommended way to start and stop GWCelery on the LIGO Data Grid cluster is
using [HTCondor]. See the example HTCondor submit file [`gwcelery.sub`]. This
submit file will start up Redis, the worker processes, and Flower. It will
create some log files and a Unix domain socket, so you should first navigate to
a directory where you want these files to go. For example:

	$ mkdir -p ~/gwcelery/var && cd ~/gwcelery/var

Then run the submit file as follows:

	$ gwcelery.sub
	Submitting job(s)......
	6 job(s) submitted to cluster 293497.

To stop GWCelery, run the `condor_hold` command:

	$ condor_hold -constraint 'JobBatchName == "gwcelery"'
	All jobs matching constraint (JobBatchName == "gwcelery") have been held

To restart GWCelery, run `condor_release`:

	$ condor_release -constraint 'JobBatchName == "gwcelery"'
	All jobs matching constraint (JobBatchName == "gwcelery") have been released

Note that there is normally **no need** to re-submit GWCelery if the machine is
rebooted, because the jobs will persist in the HTCondor queue.

## Shortcuts

The following commands are provided as shortcuts for the above operations:

    $ gwcelery condor submit
    $ gwcelery condor rm
    $ gwcelery condor q
    $ gwcelery condor hold
    $ gwcelery condor release

[HTCondor]: https://research.cs.wisc.edu/htcondor/
[`gwcelery.sub`]: https://git.ligo.org/emfollow/gwcelery/blob/master/gwcelery/data/gwcelery.sub
