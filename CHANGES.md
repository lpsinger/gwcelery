# Changelog

## 0.0.20 (2018-07-09)

-   After fixing some minor bugs in code that had not yet been tested live,
    sending VOEvents to GCN now works.

## 0.0.19 (2018-07-09)

-   Rewrite the GCN broker so that it does not require a dedicated worker.

-   Send VOEvents for preliminary alerts to GCN.

-   Only perform state vector checks for detectors that were online,
    according to the preferred event.

-   Exclude mock data challenge events from state vector checks.

## 0.0.18 (2018-07-06)

-   Add detector state vector checks to the preliminary alert workflow.

## 0.0.17 (2018-07-05)

-   Undo accidental configuration change in last version.

## 0.0.16 (2018-07-05)

-   Stop listening for three unnecessary GCN notice types:
    `SWIFT_BAT_ALARM_LONG`, `SWIFT_BAT_ALARM_SHORT`, and `SWIFT_BAT_KNOWN_SRC`.

-   Switch to [SleekXMPP](http://sleekxmpp.com) for the LVAlert client,
    instead of [PyXMPP2](http://jajcus.github.io/pyxmpp2/). Because SleekXMPP
    has first-class support for publish-subscribe, the LVAlert listener can
    now automatically subscribe to all LVAlert nodes for which our code has
    handlers. Most of the client code now lives in a new external package,
    [sleek-lvalert](https://git.ligo.org/emfollow/sleek-lvalert).

## 0.0.15 (2018-06-29)

-   Change superevent threshold and mock event rate to once per hour.

-   Add `gracedb.create_label` task.

-   Always upload external triggers to the 'External' group.

-   Add rudimentary burst event workflow to orchestrator: it just generates
    VOEvents and circulars.

-   Create a label in GraceDb whenever `em_bright` or `bayestar` completes.

## 0.0.14 (2018-06-28)

-   Fix typo that was causing a task to fail.

-   Decrease orchestrator timeout to 15 seconds.

## 0.0.13 (2018-06-28)

-   Change FAR threshold for creation of superevents to 1 per day.

-   Update ligo-followup-advocate to >= 0.0.10. Re-enable automatic generation
    of GCN circulars.

-   Add "EM bright" classification. This is rudimentary and based only on the
    point mass estimates from the search pipeline because some of the EM bright
    classifier's dependencies are not yet ready for Python 3.

-   Added logic to select CBC events as preferred event over Burst. FAR acts
    as tie breaker when groups for preferred event and new event match.

-   BAYESTAR now adds GraceDb URLs of events to FITS headers.

## 0.0.12 (2018-06-28)

-   Prevent receiving duplicate copies of LVAlert messages by unregistering
    redundant LVAlert message types.

-   Update to ligo-followup-advocate >= 0.0.9 to update GCN Circular text for
    superevents. Unfortunately, circulars are still disabled due to a
    regression in ligo-gracedb (see
    https://git.ligo.org/lscsoft/gracedb-client/issues/7).

-   Upload BAYESTAR sky maps and annotations to superevents.

-   Create (but do not send) preliminary VOEvents for all superevents.
    No vetting is performed yet.

## 0.0.11 (2018-06-27)

-   Submit handler tasks to Celery as a single group.

-   Retry GraceDb tasks that raise a `TimeoutError` exception.

-   The superevent handler now skips LVAlert messages that do not affect
    the false alarm rate of an event (e.g. simple log messages).

    (Note that the false alarm rate in GraceDb is set by the initial event
    upload and can be updated by replacing the event; however replacing the
    event does not produce an LVAlert message at all, so there is no way to
    intercept it.)

-   Added a query kwarg to superevents method to reduce latency in
    fetching the superevents from gracedb.

-   Refactored getting event information for update type events so
    that gracedb is polled only once to get the information needed
    for superevent manager.

-   Renamed the `set_preferred_event` task in gracedb.py to `update_superevent`
    to be a full wrapper around the `updateSuperevent` client function.
    Now it can be used to set preferred event and also update superevent
    time windows.

-   Many `cwb` (extra) attributes, which should be floating point
    numbers, are present in lvalert packet as strings. Casting them
    to avoid embarassing TypeErrors.

-   Reverted back the typecasting of far, gpstime into float. This is
    fixed in https://git.ligo.org/lscsoft/gracedb/issues/10

-   CBC `t_start` and `t_end` values are changed to 1 sec interval.

-   Added ligo-raven to run on external trigger and superevent creation
    lvalerts to search for coincidences. In case of coincidence, EM_COINC label
    is applied to the superevent and external trigger page and the external
    trigger is added to the list of em_events in superevent object dictionary.

-   `cwb` and `lib` nodes added to superevent handler.

-   Events are treated as finite segment window, initial superevent
    creation with preferred event window. Addition of events to
    superevents may change the superevent window and also the
    preferred event.

-   Change default GraceDb server to https://gracedb-playground.ligo.org/
    for open public alert challenge.

-   Update to ligo-gracedb >= 1.29dev1.

-   Rename the `get_superevent` task to `get_superevents` and add
    a new `get_superevent` task that is a trivial wrapper around
    `ligo.gracedb.rest.GraceDb.superevent()`.

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

-   Introduce `Production`, `Development`, `Test`, and `Playground` application
    configuration objects in order to facilitate quickly switching between
    GraceDb servers.

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
