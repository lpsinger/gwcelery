Quick start
===========

These instructions are suitable for installing GWCelery for development and
testing on any machine.

To install
----------

GWCelery requires Python >= 3.6.

The easiest way to install it is with ``venv`` and ``pip``::

    $ python -m venv --system-site-packages ~/gwcelery
    $ source ~/gwcelery/bin/activate
    $ pip install gwcelery

.. hint::
   **Note:** GWCelery requires a fairly new version of `setuptools`. If you get
   an error message that looks like this::

       pkg_resources.VersionConflict: (setuptools 0.9.8
       (/usr/lib/python2.7/site-packages),
       Requirement.parse('setuptools>=30.3.0'))

   then run ``pip install --upgrade setuptools`` and try again.


To test
-------

With ``setup.py``::

    $ python setup.py test

To start
--------

Before starting GWCelery, you need to authenticate for access to GraceDb and
LVAlert and make sure that you have a Redis server running. Once you have
completed those steps, you can start each of the GWCelery manually.

Authentication
~~~~~~~~~~~~~~

To authenticate for GraceDb, obtain grid credentials from the `LSC
DataGrid Client`_ by running ``ligo-proxy-init``::

    $ ligo-proxy-init albert.einstein

.. _`LSC DataGrid Client`: https://www.lsc-group.phys.uwm.edu/lscdatagrid/doc/installclient.html

Redis
~~~~~

GWCelery requires a `Redis`_ database server for task bookkeeping. Your
operating system's package manager may be able to install, configure, and
automatically launch a suitable Redis server for you.

.. rubric:: Debian, Ubuntu, ``apt``

Debian or Ubuntu users can install and start Redis using ``apt-get``::

    $ sudo apt-get install redis

.. rubric:: macOS, `MacPorts`_

Mac users with MacPorts can install Redis using ``port install``::

    $ sudo port install redis

Use ``port load`` to start the server::

    $ sudo port load redis

.. rubric:: From source

If none of the above options are available, then you can follow the `Redis
Quick Start`_ instructions to build redis from source and start a server::

    $ wget http://download.redis.io/redis-stable.tar.gz
    $ tar xvzf redis-stable.tar.gz
    $ cd redis-stable
    $ make -j
    $ src/redis-server

Start GWCelery components manually
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

GWCelery itself consists of four `Celery workers`_ and one `Flask`_ web
application. Start them all by running each of the following commands::

    $ gwcelery worker -l info -n gwcelery-worker -Q celery -B
    $ gwcelery worker -l info -n gwcelery-openmp-worker -Q openmp -c 1
    $ gwcelery worker -l info -n gwcelery-superevent-worker -Q superevent -c 1
    $ gwcelery worker -l info -n gwcelery-exttrig-worker -Q exttrig -c 1
    $ gwcelery flask run

.. hint::
   With these arguments, each of the commands above will run until you type
   Control-C. You may want to run each of them in a separate terminal, or in
   the background using `screen`_ or `nohup`_.

.. _`redis`: https://redis.io
.. _`MacPorts`: https://www.macports.org
.. _`Redis Quick Start`: https://redis.io/topics/quickstart
.. _`Celery workers`: http://docs.celeryproject.org/en/latest/userguide/workers.html
.. _`Flask`: http://flask.pocoo.org
.. _`screen`: https://linux.die.net/man/1/screen
.. _`nohup`: https://linux.die.net/man/1/nohup
