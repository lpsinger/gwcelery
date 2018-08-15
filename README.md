![GWCelery logo](https://gwcelery.readthedocs.io/en/latest/_static/logo-0.5x.png)

# GWCelery

GWCelery is a simple and reliable package for annotating and orchestrating
LIGO/Virgo alerts, built from widely used open source components.

See the [quick start installation instructions](https://gwcelery.readthedocs.io/en/latest/quickstart.html),
the full [documentation](https://gwcelery.readthedocs.io/en/latest/), or the
[contributing guide](https://gwcelery.readthedocs.io/en/latest/contributing.html).

## Features

 - [Easy installation with `pip`](https://gwcelery.readthedocs.io/en/latest/quickstart.html)
 - Lightning fast distributed task queue powered by
   [Celery](http://celeryproject.org) and [Redis](https://redis.io)
 - Tasks are defined by [small, self-contained Python functions](https://git.ligo.org/emfollow/gwcelery/tree/master/gwcelery/tasks)
 - [Lightweight test suite](https://git.ligo.org/emfollow/gwcelery/tree/master/gwcelery/tests) using mocks of external services
 - [Continuous integration](https://git.ligo.org/emfollow/gwcelery/pipelines)
 - [One environment variable to switch from playground to production GraceDB server](https://gwcelery.readthedocs.io/en/latest/configuration.html)
 - [Browser-based monitoring console](https://gwcelery.readthedocs.io/en/latest/monitoring.html)
