# GWCelery

Hipster pipeline for annotating LIGO events.

## Instructions

## To install

With `pip`:

	$ pip install --user git+https://git.ligo.org/leo-singer/gwcelery

## To start

You need to start two workers:

	$ gwcelery worker -Q celery -n gwcelery-worker -B -l info
	$ gwcelery worker -c 1 -Q openmp -n gwcelery-openmp-worker -l info

The `condor` directory provides some example condor submit files.

## To monitor in a browser

	$ gwcelery flower
