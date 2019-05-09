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
the GraceDB and LVAlert service URLs, GCN hostnames, and frame file types and
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
tokens for GraceDB and LValert.

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

.. rubric:: LVAlert

You must provide a valid username and password for LVAlert. You can request an
account using the `LVAlert Account Activation`_ form. The LVAlert username and
password should be stored in your `netrc file`_.

.. _`LSC DataGrid Client`: https://www.lsc-group.phys.uwm.edu/lscdatagrid/doc/installclient.html
.. _`obtain a robot certificate`: https://robots.ligo.org
.. _`LVAlert Account Activation`: https://www.lsc-group.phys.uwm.edu/cgi-bin/jabber-acct.cgi
.. _`netrc file`: https://www.gnu.org/software/inetutils/manual/html_node/The-_002enetrc-file.html
