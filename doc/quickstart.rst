.. highlight:: shell-session

Quick start
===========

These instructions are suitable for installing GWCelery for development and
testing on any machine.

GWCelery requires Python >= 3.7 and a Linux or UNIX-like operating system. It
does not support Windows.

To install
----------

GWCelery uses `Poetry`_ for packaging, dependency tracking, and virtual
environment management; and the `poetry-dynamic-versioning`_ plugin for
synchronizing the package's version number with Git tags. First, install these
two tools if you do not already have them.

1. Run the following command to `install Poetry using the recommended method`_::

    $ curl -sSL https://install.python-poetry.org | python3 -

2. Then, install poetry-dynamic-versioning using pip::

    $ pip install poetry-dynamic-versioning

3. Run these commands to clone the GWCelery git repository::

    $ git clone https://git.ligo.org/emfollow/gwcelery.git
    $ cd gwcelery

4. Inside the cloned git repository, run this command to create a
   Poetry-managed virtual environment containing GWCelery and all of its
   dependencies::

    $ poetry install

5. Now, whenever you want to enter a shell within the virtual environment, run
   this command inside the git clone directory::

    $ poetry shell

.. _`Poetry`: https://python-poetry.org
.. _`poetry-dynamic-versioning`: https://github.com/mtkennerly/poetry-dynamic-versioning
.. _`install Poetry using the recommended method`: https://python-poetry.org/docs/#osx--linux--bashonwindows-install-instructions

To test
-------

First, install the extra test dependencies in the Poetry-managed virtual
environment by running this command::

    $ poetry install --extras=test

Then, to run the unit tests, just run pytest within the Poetry virtual
environment::

    $ poetry shell
    $ pytest

As a shortcut, you can use ``poetry run`` to execute a single command within
the virtual environment, like this::

    $ poetry run pytest

To start
--------

Before starting GWCelery, you need to authenticate for access to GraceDB and
IGWN Alert and make sure that you have a Redis server running. Once you have
completed those steps, you can start each of the GWCelery manually.

Authentication
~~~~~~~~~~~~~~

To authenticate for GraceDB, obtain grid credentials from the `LSC
DataGrid Client`_ by running ``ligo-proxy-init``::

    $ ligo-proxy-init albert.einstein

To authenticate for :doc:`IGWN Alert <igwn-alert:index>`, create an account in `SCiMMA Auth portal`_, and
follow the necessary steps in the :doc:`IGWN Alert Users Guide <igwn-alert:guide>`. Make a note of the
passwords and store them in your ~/.netrc file with appropriate file permissions::

    $ echo > ~/.netrc
    $ chmod 0600 ~/.netrc
    $ echo machine kafka://kafka.scimma.org/ login albert.einstein password password-for-production >> ~/.netrc
    $ echo machine kafka://kafka.scimma.org/ login albert.einstein password password-for-playground >> ~/.netrc
    $ echo machine kafka://kafka.scimma.org/ login albert.einstein password password-for-test >> ~/.netrc

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

GWCelery itself consists of five :ref:`Celery workers <celery:guide-workers>`
and one `Flask`_ web application. Start them all by running each of the
following commands::

    $ gwcelery worker -l info -n gwcelery-worker -Q celery -B --igwn-alert
    $ gwcelery worker -l info -n gwcelery-exttrig-worker -Q exttrig -c 1
    $ gwcelery worker -l info -n gwcelery-openmp-worker -Q openmp -c 1
    $ gwcelery worker -l info -n gwcelery-superevent-worker -Q superevent -c 1
    $ gwcelery worker -l info -n gwcelery-voevent-worker -Q voevent -P solo
    $ gwcelery flask run

.. hint::
   With these arguments, each of the commands above will run until you type
   Control-C. You may want to run each of them in a separate terminal, or in
   the background using `screen`_ or `nohup`_.

.. _`redis`: https://redis.io
.. _`MacPorts`: https://www.macports.org
.. _`Redis Quick Start`: https://redis.io/topics/quickstart
.. _`Flask`: http://flask.pocoo.org
.. _`screen`: https://linux.die.net/man/1/screen
.. _`nohup`: https://linux.die.net/man/1/nohup
.. _`SCiMMA Auth portal`: https://my.hop.scimma.org/

