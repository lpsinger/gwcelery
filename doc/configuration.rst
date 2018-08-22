Configuration
=============

By default, GWCelery will talk to the playground GraceDb server,
``gracedb-playground.ligo.org``. To switch to using the production GraceDb
server, ``gracedb.ligo.org``, set the following environment variable before
starting GWCelery::

    CELERY_CONFIG_MODULE=gwcelery.conf.production

For further customization, see the API documentation for the
:mod:`gwcelery.conf` module.
