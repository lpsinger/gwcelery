![GWCelery logo](doc/_static/logo-0.5x.png)

# GWCelery

| **Build** | **Test** | **Docs** |
| :-: | :-: | :-: |
| [![build status](https://git.ligo.org/emfollow/gwcelery/badges/master/build.svg)](https://git.ligo.org/emfollow/gwcelery/pipelines) | [![coverage report](https://git.ligo.org/emfollow/gwcelery/badges/master/coverage.svg)](https://emfollow.docs.ligo.org/gwcelery/htmlcov) | [Latest](https://emfollow.docs.ligo.org/gwcelery/) |

GWCelery is a simple and reliable package for annotating and orchestrating LIGO/Virgo alerts, built from widely used open source components.

See the [quick start installation instructions](https://emfollow.docs.ligo.org/gwcelery/quickstart.html), the full [documentation](https://emfollow.docs.ligo.org/gwcelery/), or the
[contributing guide](https://emfollow.docs.ligo.org/gwcelery/contributing.html).

## Features

 - [Easy installation with `pip`](https://emfollow.docs.ligo.org/gwcelery/quickstart.html)
 - Lightning fast distributed task queue powered by
   [Celery](http://celeryproject.org) and Redis (https://redis.io)
 - Tasks are defined by [small, self-contained Python functions](https://git.ligo.org/emfollow/gwcelery/tree/master/gwcelery/tasks)
 - [Lightweight test suite](https://git.ligo.org/emfollow/gwcelery/tree/master/gwcelery/tests) using mocks of external services
 - [Continuous integration](https://git.ligo.org/emfollow/gwcelery/pipelines)
 - [One line of code to switch from test to production GraceDB server](https://git.ligo.org/emfollow/gwcelery/blob/master/gwcelery/celery.py)
 - [Browser-based monitoring console](https://emfollow.docs.ligo.org/gwcelery/monitoring.html)
