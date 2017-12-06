# Running under HTCondor

The recommended way to start and stop GWCelery on the LIGO Data Grid cluster is
using [HTCondor](https://research.cs.wisc.edu/htcondor/). See the example
HTCondor submit file [`etc/gwcelery.sub`](etc/gwcelery.sub). This submit file
will start up Redis, the three worker processes, and Flower. To start, go into
the `etc/` directory in the source tree and run `condor_submit` as follows:

	$ condor_submit gwcelery.sub
	Submitting job(s).....
	5 job(s) submitted to cluster 293497.

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
