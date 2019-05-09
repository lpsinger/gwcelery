.. highlight:: shell-session

Contributing
============

Contributors may familiarize themselves with Celery itself by going through the
:ref:`celery:first-steps` tutorial.

Development model
-----------------

GWCelery operates on a fork-and-merge development model (see `GitLab basics`_
for an introduction).

To contribute to GWCelery development, follow these steps:

1.  `Create a personal fork of GWCelery`_.
2.  Make your changes on a branch.
3.  Open a merge request.

Note that GWCelery uses `fast-forward merges`_.

.. _`GitLab basics`: https://git.ligo.org/help/gitlab-basics/README.md
.. _`Create a personal fork of GWCelery`: https://git.ligo.org/emfollow/gwcelery/forks/new
.. _`fast-forward merges`: https://git.ligo.org/help/user/project/merge_requests/fast_forward_merge.md

Where new code should go
------------------------

New code will generally consist of adding :ref:`Celery tasks <celery:guide-tasks>`.
Tasks are organized by functionality into submodules of :mod:`gwcelery.tasks`.
If your new task does not match with one of the existing submodules, please
create a new submodule.

Guidelines for tasks
--------------------

-  **Tasks should be short.** When deciding where a new task should go, start
   from the following loose rules of thumb:

   1.  If it's less than a screenful of code, and related to functionality in
       an existing module, then put the code in a new task in that module.

   2.  If it's up to a few screenfuls of code, or not related to functionality
       in an existing module, then try to break it into a few smaller functions
       or tasks and put it in a new module.

   3.  If it's more than a few screenfuls of code, or adds many additional
       dependencies, then it should go in a separate package.

   See also the note on :ref:`celery:task-granularity` in the Celery manual's
   :ref:`celery:task-best-practices` section.

-  **Tasks should avoid saving files to disk.** Output should be placed
   directly in GraceDB. Temporary files that are written in ``/tmp`` are OK but
   should be cleaned up promptly.

   See also the Celery manual's notes on :ref:`celery:task-data-locality` and
   :ref:`celery:task-state`.

-  **Dependencies should be installable by pip.** Dependencies of tasks should
   be listed in the `requirements.txt`_ file so that they are installed
   automatically when GWCelery is installed with `pip`_.

   There are two extra steps involved in making changes to the dependencies:

   1.  The Sphinx-generated documentation (that is to say, this manual) is
       generally built without most of the dependencies installed. Whenever you
       add a new package to requirements.txt, you should also add any modules
       that are imported from that package to the ``autodoc_mock_imports`` list
       in the Sphinx configuration file, `doc/conf.py`_.

   2.  We use `pipenv`_ to make the precise versions of packages reproducible
       in our deployment. If you make changes to requirements.txt, then run
       ``pipenv update`` and commit the changes to `Pipfile.lock`_.

.. _`requirements.txt`: https://git.ligo.org/emfollow/gwcelery/blob/master/requirements.txt
.. _`doc/conf.py`: https://git.ligo.org/emfollow/gwcelery/blob/master/doc/conf.py
.. _`Pipfile.lock`: https://git.ligo.org/emfollow/gwcelery/blob/master/Pipfile.lock
.. _`pip`: https://pip.pypa.io/
.. _`pipenv`: https://pipenv.readthedocs.io/

Unit tests
----------

Unit tests and code coverage measurement are run automatically for every branch
and for every merge request. New code contributions must have 100% test
coverage. Modifications to existing code must not decrease test coverage. To
run the unit tests and measure code coverage, run the following commands in the
top directory of your local source checkout::

    $ pip install pytest-cov
    $ python setup.py test --addopts='--cov --cov-report html'

This will save a coverage report that you can view in a web browser as
``htmlcov/index.html``.

Code style
----------

Code should be written in the :pep:`8` style and must pass linting by
`Flake8`_. To check code style, run the following commands in the top of your
source directory::

    $ pip install flake8 pep8-naming
    $ flake8 --show-source .

.. _Flake8: http://flake8.pycqa.org/en/latest/

Documentation
-------------

Documentation strings should be written in the `Numpydoc style`_.

To build the documentation, run the following command in the top of your source
directory::

    $ python setup.py build_sphinx

Then to view the documentation, open the file ``build/sphinx/html/index.html``
in your favorite web browser.

.. _`Numpydoc style`: http://numpydoc.readthedocs.io/
