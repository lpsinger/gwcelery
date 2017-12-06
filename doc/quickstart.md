# Quick start

## To install

With `pip`:

	$ pip install --user git+https://git.ligo.org/emfollow/gwcelery

## To test

With `setup.py`:

	$ python setup.py test

## To start

**NOTE** that GWCelery requires [redis](https://redis.io). Your package manager
(apt, yum, macports) should be able to install, configure, and automatically
launch a suitable redis server, but otherwise you can use the
[Redis Quick Start](https://redis.io/topics/quickstart) instructions to build
redis and start a server:

	$ wget http://download.redis.io/redis-stable.tar.gz
	$ tar xvzf redis-stable.tar.gz
	$ cd redis-stable
	$ make -j
	$ src/redis-server

GWCelery itself consists of three workers:

	$ gwcelery worker -Q celery -n gwcelery-worker -B -l info
	$ gwcelery worker -c 1 -Q openmp -n gwcelery-openmp-worker -l info
	$ gwcelery worker -c 1 -Q voevent -n gwcelery-voevent-worker -l info
