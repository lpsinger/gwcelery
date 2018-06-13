# Changelog

## 0.0.10 (2018-06-13)

-   Model the time extent of events and superevents using the
    `glue.segments` module.

-   Replace GraceDb.get with GraceDb.superevents from the recent dev
    release of gracedb-client.

-   Fix possible false positive matches between GCNs for unrelated GRBs
    by matching on both TrigID (which is generally the mission elapsed time)
    and mission name.

-   Add the configuration variable `superevent_far_threshold` to limit
    the maximum false alarm rate of events that are included in superevents.

-   LVAlert handlers are now passed the actual alert data structure rather than
    the JSON text, so handlers are no longer responsible for calling
    `json.loads`. It is a little bit more convenient and possibly also faster
    for Celery to deserialize the alert messages.

-   Introduce ``Production``, ``Development``, ``Test``, and ``Playground``
    application configuration objects in order to facilitate quickly switching
    between GraceDb servers.

-   Pipeline specific start and end times for superevent segments. These values
    are controlled via configuration variables.

## 0.0.9 (2018-06-06)

-   Add missing LVAlert message types to superevent handler.

## 0.0.8 (2018-06-06)

-   Add some logging to the GCN and LVAlert dispatch code in order to
    diagnose missed messages.

## 0.0.7 (2018-05-31)

-   Ingest Swift, Fermi, and SNEWS GCN notices and save them in GraceDb.

-   Depend on the pre-release version of the GraceDb client, ligo-gracedb
    1.29.dev0, because this is the only version that supports superevents at
    the moment.

## 0.0.6 (2018-05-26)

-   Generate GCN Circular drafts using
    [``ligo-followup-advocate``](https://git.ligo.org/emfollow/ligo-followup-advocate).

-   In the continuous integration pipeline, validate PEP8 naming conventions
    using [``pep8-naming``](https://pypi.org/project/pep8-naming/).

-   Add instructions for measuring test coverage and running the linter locally
    to the contributing guide.

-   Rename `gwcelery.tasks.voevent` to `gwcelery.tasks.gcn` to make it clear
    that this submodule contains functionality related to GCN notices,
    rather than VOEvents in general.

-   Rename `gwcelery.tasks.dispatch` to `gwcelery.tasks.orchestrator` to make
    it clear that this module encapsulates the behavior associated with the
    "orchestrator" in the O3 low-latency design document.

-   Mock up calls to BAYESTAR in test suite to speed it up.

-   Unify dispatch of LVAlert and GCN messages using decorators.
    GCN notice handlers are declared like this:

        import lxml.etree
        from gwcelery.tasks import gcn

        @gcn.handler(gcn.NoticeType.FERMI_GBM_GND_POS,
                     gcn.NoticeType.FERMI_GBM_FIN_POS)
        def handle_fermi(payload):
            root = lxml.etree.fromstring(payload)
            # do work here...

    LVAlert message handlers are declared like this:

        import json
        from gwcelery.tasks import lvalert

        @lvalert.handler('cbc_gstlal',
                         'cbc_pycbc',
                         'cbc_mbta')
        def handle_cbc(alert_content):
            alert = json.loads(alert_content)
            # do work here...

-   Instead of carrying around the GraceDb service URL in tasks, store the
    GraceDb host name in the Celery application config.

-   Create superevents by simple clustering in time. Currently this is only
    supported by the `gracedb-dev1` host.

## 0.0.5 (2018-05-08)

-   Disable socket access during most unit tests. This adds some extra assurance
    that we don't accidentally interact with production servers during the unit
    tests.

-   Ignore BAYESTAR jobs that raise a ``DetectorDisabled`` error. These
    exceptions are used for control flow and do not constitute a real error.
    Ignoring these jobs avoids polluting logs and the Flower monitor.

## 0.0.4 (2018-04-28)

-   FITS history and comment entries are now displayed in a monospaced font.

-   Adjust error reporting for some tasks.

-   Depend on newer version of ``ligo.skymap``.

-   Add unit tests for the ``gwcelery condor submit`` subcommand.

## 0.0.3 (2018-04-27)

-   Fix some compatibility issues between the ``gwcelery condor submit``
    subcommand and the format of ``condor_q -totals -xml`` with older versions
    of HTCondor.

## 0.0.2 (2018-04-27)

-   Add `gwcelery condor submit` and related subcommands as shortcuts for
    managing GWCelery running under HTCondor.

## 0.0.1 (2018-04-27)

-   This is the initial release. It provides rapid sky localization with
    BAYESTAR, sky map annotation, and sending mock alerts.

-   By default, GWCelery is configured to listen to the test LVAlert server.

-   Sending VOEvents to GCN/TAN is disabled for now.
