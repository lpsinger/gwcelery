# Quick start

## To install

With `virtualenv` and `pip`:

	$ virtualenv --system-site-packages ~/gwcelery
	$ source ~/gwcelery/bin/activate
	$ pip install git+https://git.ligo.org/emfollow/gwcelery

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

	$ gwcelery worker -l info -n gwcelery-worker -Q celery -B
	$ gwcelery worker -l info -n gwcelery-openmp-worker -Q openmp -c 1
	$ gwcelery worker -l info -n gwcelery-voevent-worker -Q voevent -c 1
