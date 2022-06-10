.. highlight:: shell-session

Configuration
=============

Like any Celery application, GWCelery's configuration options are stored at run
time in a global configuration object, :obj:`gwcelery.app.conf`. There are
options for Celery itself such as options that affect the task and result
backends; these options are documented in the :ref:`celery:configuration`
section of the Celery manual.

The configuration object also holds all of the options that are specific to
GWCelery and affect the behavior of individual GWCelery tasks; examples include
the GraceDB service URLs, IGWN Alert groups, GCN hostnames, and frame file types and
channel names. For a list of all GWCelery-specific options, see the
API documentation for the :mod:`gwcelery.conf` module.

GWCelery provides four preset configurations, one for each GraceDB server
instance (production, deployment, testing, or playground). The default
configuration preset is for the playground server,
``gracedb-playground.ligo.org``. The recommended way to select a different
preset is to set the :meth:`CELERY_CONFIG_MODULE
<celery.Celery.config_from_envvar>` environment variable before starting the
workers. For example, to configure GWCelery for production::

    $ export CELERY_CONFIG_MODULE=gwcelery.conf.production

Authentication
--------------

There are a few files that must be present in order to provide authentication
tokens for GraceDB and :doc:`IGWN Alert <igwn-alert:index>`.

.. rubric:: GraceDB

You must provide valid LSC DataGrid credentials in order for requests to the
GraceDB REST API to work. During development and testing, you can use your
personal credentials obtained from the `LSC DataGrid Client`_ by running
``ligo-proxy-init``. However, credentials obtained this way expire after a few
days or whenever your machine's temporary directory is wiped (e.g., at system
restart).

For production deployment, you should `obtain a robot certificate`_ and store
it in a location such as ``~/.globus/userkey.pem`` and
``~/.globus/usercert.pem``.

.. rubric:: IGWN Alert

You must provide a valid username and password for :doc:`IGWN Alert <igwn-alert:index>`. You can request an
account using the `SCiMMA Auth portal`_. To get started, see :doc:`IGWN Alert Userguide <igwn-alert:guide>`.
The IGWN Alert username and password should be stored in your `netrc file`_.

.. _`LSC DataGrid Client`: https://www.lsc-group.phys.uwm.edu/lscdatagrid/doc/installclient.html
.. _`obtain a robot certificate`: https://robots.ligo.org
.. _`SCiMMA Auth portal`: https://my.hop.scimma.org/
.. _`netrc file`: https://www.gnu.org/software/inetutils/manual/html_node/The-_002enetrc-file.html

.. _redis-configuration:

Redis
-----

We recommend that you make the following settings in your Redis server
configuration file (which is located at :file:`/etc/redis.conf` on most
systems)::

    # Some GWCelery tasks transfer large payloads through Redis.
    # The default Redis client bandwidth limits are too small.
    client-output-buffer-limit normal 0 0 0
    client-output-buffer-limit slave 256mb 64mb 60
    client-output-buffer-limit pubsub 256mb 64mb 60

    # If worker nodes are only reachable on a specific network interface,
    # then make sure to bind any additional IP addresses here.
    bind 127.0.0.1 10.0.0.1  # replace 10.0.0.1 with address on cluster network

    # Disable RDB snapshots.
    save ""

    # Enable appendonly snapshots.
    appendonly yes

If you have to make any changes to your Redis configuration, be sure to restart
the Redis daemon.
