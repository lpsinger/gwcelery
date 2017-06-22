# GWCelery

[![build status](https://git.ligo.org/leo-singer/gwcelery/badges/master/build.svg)](https://git.ligo.org/leo-singer/gwcelery/commits/master)
[![coverage report](https://git.ligo.org/leo-singer/gwcelery/badges/master/coverage.svg)](https://git.ligo.org/leo-singer/gwcelery/commits/master)

Hipster pipeline for annotating LIGO events.

## Features

 - Easy installation with `pip`
 - Lightning fast distributed task queue powered by
   [Celery](http://celeryproject.org) and Redis (https://redis.io).
 - Lightweight test suite using mocks of external services
 - One line of code to switch from test to production GraceDB server
 - Browser-based monitoring console (see below)

## Instructions

### To install

With `pip`:

	$ pip install --user git+https://git.ligo.org/leo-singer/gwcelery

### To test

With `setup.py`:

	$ python setup.py test

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

For an example HTCondor submit file, see the file `etc/gwcelery.sub`.

### To monitor in a browser

	$ gwcelery flower
