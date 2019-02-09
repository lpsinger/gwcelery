.. image:: https://gwcelery.readthedocs.io/en/latest/_static/logo-0.5x.png
   :alt: GWCelery logo

GWCelery
========

GWCelery is a simple and reliable package for annotating and orchestrating
LIGO/Virgo alerts, built from widely used open source components.

See the `quick start installation instructions <https://gwcelery.readthedocs.io/en/latest/quickstart.html>`_,
the full `documentation <https://gwcelery.readthedocs.io/en/latest/>`_, or the
`contributing guide <https://gwcelery.readthedocs.io/en/latest/contributing.html>`_.

Features
--------

- `Easy installation with pip <https://gwcelery.readthedocs.io/en/latest/quickstart.html>`_
- Lightning fast distributed task queue powered by
  `Celery <http://celeryproject.org>`_ and `Redis <https://redis.io>`_
- Tasks are defined by `small, self-contained Python functions <https://git.ligo.org/emfollow/gwcelery/tree/master/gwcelery/tasks>`_
- `Lightweight test suite <https://git.ligo.org/emfollow/gwcelery/tree/master/gwcelery/tests>`_ using mocks of external services
- `Continuous integration <https://git.ligo.org/emfollow/gwcelery/pipelines>`_
- `One environment variable to switch from playground to production GraceDB server <https://gwcelery.readthedocs.io/en/latest/configuration.html>`_
- `Browser-based monitoring console <https://gwcelery.readthedocs.io/en/latest/monitoring.html>`_
