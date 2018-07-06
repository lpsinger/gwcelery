# Quick start

## To install

GWCelery requires Python >= 3.5.

The easiest way to install it is with `virtualenv` and `pip`:

	$ virtualenv --system-site-packages ~/gwcelery
	$ source ~/gwcelery/bin/activate
	$ pip install git+https://git.ligo.org/emfollow/gwcelery

*  **Note:** GWCelery requires a fairly new version of `setuptools`. If you get
   an error message that looks like this:

       pkg_resources.VersionConflict: (setuptools 0.9.8 (gwcelery/lib/python2.7/site-packages), Requirement.parse('setuptools>=30.3.0'))

   then run `pip install --upgrade setuptools` and try again.


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

GWCelery itself consists of four workers:

	$ gwcelery worker -l info -n gwcelery-worker -Q celery -B
	$ gwcelery worker -l info -n gwcelery-openmp-worker -Q openmp -c 1
	$ gwcelery worker -l info -n gwcelery-superevent-worker -Q superevent -c 1
        $ gwcelery worker -l info -n gwcelery-exttrig-worker -Q exttrig -c 1
