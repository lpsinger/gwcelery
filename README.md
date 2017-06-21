# GWCelery

Hipster pipeline for annotating LIGO events.

## Features

 - Lightning fast distributed task queue powered by
   [Celery](http://celeryproject.org) and Redis (https://redis.io).
 - Easy installation with `pip`
 - Browser-based monitoring console (see below)

## Instructions

### To install

With `pip`:

	$ pip install --user git+https://git.ligo.org/leo-singer/gwcelery

### To start

**NOTE** that GWCelery requires redis. Your package manager (apt, yum, macports)
should be able to provide a suitable pre-configured redis server, but otherwise
you can use the [Redis Quick Start](https://redis.io/topics/quickstart)
instructions to build redis and start a server:

	$ wget http://download.redis.io/redis-stable.tar.gz
	$ tar xvzf redis-stable.tar.gz
	$ cd redis-stable
	$ make -j
	$ src/redis-server

GWCelery itself consists of two workers:

	$ gwcelery worker -Q celery -n gwcelery-worker -B -l info
	$ gwcelery worker -c 1 -Q openmp -n gwcelery-openmp-worker -l info

The `condor` directory provides some example condor submit files.

### To monitor in a browser

	$ gwcelery flower
