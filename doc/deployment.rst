Deployment
==========

Continuous deployment
---------------------

GWCelery is automatically deployed using GitLab's continuous deployment
features, configured through the project's `.gitlab-ci.yml`_ file. Deployment
can be managed through the GitLab project's `Environments`_ page.

Python dependencies in the deployment environment are managed automatically
using `pipenv`_.

There are two instances of GWCelery that are running on the LIGO-Caltech
computing cluster and that are managed in this manner:

*   **Playground**: The playground instance is re-deployed *on every push to
    master that passes the unit tests*. It uses the
    :mod:`gwcelery.conf.playground` configuration preset.

*   **Production**: The production instance is re-deployed *only when manually
    triggered through GitLab*. It uses the
    :mod:`gwcelery.conf.production` configuration preset.

When we observe that the Playground instance shows correct end-to-end behavior,
we have the option of triggering a re-deployment to Production. Deployment to
production should preferably occur at a release. The procedure for performing a
release is described below.

.. danger::
   It is possible to start an interactive session inside the GWCelery
   production environment by logging in to the LIGO-Caltech cluster, but this
   measure should be **reserved for emergencies only**.

   Any manual changes to the environment **may disrupt the logging and
   monitoring subsystems**. Any files that are manually changed, added to, or
   removed from the deployment environment **will not be captured in version
   control** and may be **rolled back without warning** the next time that the
   continuous deployment is triggered.

Making a new release
--------------------

We always prepare releases from the tip of the ``master`` branch. GitLab is
configured through the project's `.gitlab-ci.yml`_ file to automatically build
and push any tagged release to the `Python Package Index`_ (PyPI). Follow these
steps when issuing a release in order to maintain a consistent and orderly
change log.

1.  **Check the pipeline status.** Before you begin, first make sure that the
    unit tests, documentation, and packaging jobs are passing. Consult the
    project's `GitLab pipeline status`_ to make sure that all of the continuous
    integration jobs are passing on ``master``.

    If necessary, fix any bugs that are preventing the pipeline from passing,
    push the changes to master, and repeat until all jobs pass.

2.  **Update the change log.** The first subsection of the change log file,
    `CHANGES.rst`_, should have the title :samp:`{MAJOR.MINOR.PATCH}
    (unreleased)`, where :samp:`{MAJOR.MINOR.PATCH}` will be the version number
    of the new release. Review the git commit log.

    Make any necessary changes to CHANGES.rst so that this
    subsection of the change log accurately summarizes all of the significant
    changes since the last release and is free of spelling, grammatical, or
    reStructuredText formatting errors.

    Review the list of changes and make sure that the new version number is
    appropriate. We follow `SemVer`_ *very* loosely, and also generally bump at
    least the minor version number at the start of a new LSC/Virgo engineering
    or observing run.

    Commit and push any corrections to CHANGES.rst to ``master``.

3.  **Complete the acceptance tests.** Our acceptance tests
    consist of a manual checklist for verifying that the pipeline satisfies
    certain requirements on the playground environment. The checklist is
    maintained as a GitLab `issue template`_ and is under version control in
    the special directory `.gitlab/issue_templates`_.

    Create a `new issue`_ in GitLab. Set the title to :samp:`Release version
    {MAJOR.MINOR.PATCH}`. In the ``Choose a template`` dropdown menu, select
    ``Create a Release``. The description field will be automatically populated
    with the checklist. Submit the issue.

    Complete the items in the checklist and check them off one by one on the
    release issue before proceeding to the next step.

    .. image:: _static/acceptance-tests-checklist.png
       :alt: Screen shot of a release issue

4.  **Tag the release.** Change the title of the first section of
    CHANGES.rst to :samp:`{MAJOR.MINOR.PATCH} ({YYYY-MM-DD})` where
    :samp:`{YYYY-MM-DD}` is today's date. Commit with the message :samp:`Update
    changelog for version {MAJOR.MINOR.PATCH}; closes #{N}`, where :samp:`{N}`
    is the release issue's number.

    Create a git tag to mark the release by running the following command:

        :samp:`$ git tag v{MAJOR.MINOR.PATCH} -m "Version {MAJOR.MINOR.PATCH}"`

5.  **Create a change log section for the next release.** Add a new section to
    CHANGES.rst with the title :samp:`{NEXT_MAJOR.NEXT_MINOR.NEXT_PATCH}
    (unreleased)`, where :samp:`{NEXT_MAJOR.NEXT_MINOR.NEXT_PATCH}` is a
    provisional version number for the next release. Add a single list item
    with the text ``No changes yet.`` Commit with the message ``Back to
    development.``

6.  **Push the new tag and updated change log.** Push the new tag and updated
    change log:

        ``git push && git push --tags``

7.  Wait a couple minutes, and then verify that the new release has been
    published on our PyPI project page, https://pypi.org/project/gwcelery/.

8.  If desired, navigate to the GitLab project's `Environments`_ page and
    trigger a deployment to production.

.. _`Environments`: https://git.ligo.org/emfollow/gwcelery/environments
.. _`.gitlab-ci.yml`: https://git.ligo.org/emfollow/gwcelery/blob/master/.gitlab-ci.yml
.. _`pipenv`: https://pipenv.readthedocs.io/
.. _`Python Package Index`: https://pypi.org
.. _`GitLab pipeline status`: https://git.ligo.org/emfollow/gwcelery/pipelines
.. _`CHANGES.rst`: https://git.ligo.org/emfollow/gwcelery/blob/master/CHANGES.rst
.. _`SemVer`: https://semver.org
.. _`issue template`: https://docs.gitlab.com/ee/user/project/description_templates.html
.. _`.gitlab/issue_templates`: https://git.ligo.org/emfollow/gwcelery/tree/master/.gitlab/issue_templates
.. _`new issue`: https://git.ligo.org/emfollow/gwcelery/issues/new