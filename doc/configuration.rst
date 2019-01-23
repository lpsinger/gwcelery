Configuration
=============

Many GWCelery tasks have configuration options that can be set to adjust their
behavior. All options are stored at run time in the Celery application's global
configuration object. As with any Celery application, :doc:`configuration
settings can be loaded from a Python module or object
<celery:userguide/application>`.

The most important settings are those that determine which GraceDb and LVAlert
servers GWCelery should talk to. GWCelery provides a small collection of
preset configuration modules for different GraceDb/LVAlert servers (production,
deployment, testing, or playground). The default is the playground server,
``gracedb-playground.ligo.org``. To switch to using the production GraceDb
server, ``gracedb.ligo.org``, set the following environment variable before
starting GWCelery::

    CELERY_CONFIG_MODULE=gwcelery.conf.production

For a list of all configuration options and preset modules, see the API
documentation for the :mod:`gwcelery.conf` module.
