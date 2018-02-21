# Contributing

Contributors may familiarize themselves with Celery itself by going through the
[First Steps with Celery](http://docs.celeryproject.org/en/latest/getting-started/first-steps-with-celery.html) tutorial.

## Where new code should go

New code will generally consist of adding [Celery tasks](http://docs.celeryproject.org/en/latest/userguide/tasks.html).
Tasks are organized by functionality into submodules of `gwcelery.tasks`. If
your new task does not match with one of the existing submodules, please create
a new submodule.

## Guidelines for tasks

-  Celery tasks should delegate as much functionality as possible to external
   packages. Ideally, a new Celery task should simply call a function that is
   provided by an external package such as lalsuite, pycbc, or a new
   self-contained software project.

-  Dependencies of tasks should be listed in the `install_requires` section in
   [`setup.cfg`](https://git.ligo.org/emfollow/gwcelery/blob/master/setup.cfg)
   so that they are installed automatically when GWCelery is installed with
   [`pip`](https://pip.pypa.io/).

## Development model

GWCelery operates on a fork-and-merge development model (see
[GitLab basics](https://git.ligo.org/help/gitlab-basics/README.md) for an
introduction).

Unit tests and code coverage measurement are run automatically for every branch
and for every merge request. New code contributions must have 100% test
coverage. Modifications to existing code must not decrease test coverage.
Code should be written in the
[PEP 8 style](https://www.python.org/dev/peps/pep-0008/).

To contribute to GWCelery development, follow these steps:

1.  [Create a personal fork of GWCelery](https://git.ligo.org/emfollow/gwcelery/forks/new).
2.  Make your changes on a branch.
3.  Open a merge request.

Note that GWCelery uses
[fast-forward merges](https://git.ligo.org/help/user/project/merge_requests/fast_forward_merge.md).
