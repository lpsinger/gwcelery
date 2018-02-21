# Running under HTCondor

The recommended way to start and stop GWCelery on the LIGO Data Grid cluster is
using [HTCondor](https://research.cs.wisc.edu/htcondor/). See the example
HTCondor submit file [`gwcelery.sub`](_static/gwcelery.sub). This submit file
will start up Redis, the worker processes, and Flower. It will create some log
files and a Unix domain socket, so you should first navigate to a directory
where you want these files to go. For example:

    $ mkdir -p ~/var/gwcelery && cd ~/var/gwcelery

Then run the submit file as follows:

	$ ~/src/gwcelery/doc/_static/gwcelery.sub
	Submitting job(s)......
	6 job(s) submitted to cluster 293497.

Make note of the cluster number on the last line. To stop GWCelery, run the
`condor_hold` command:

	$ condor_hold 293497
	All jobs in cluster 293497 have been held

To restart GWCelery, run `condor_release`:

	$ condor_release 293497
	All jobs in cluster 293497 have been released

Note that there is normally **no need** to explicitly kill or re-submit
GWCelery if the machine is rebooted, because the jobs will persist in the
HTCondor queue.
