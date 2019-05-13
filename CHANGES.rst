Changelog
=========

0.5.7 (2019-05-13)
------------------

-   If the VOEvent broker is disabled by setting ``voevent_broker_whitelist``
    to an empty list, then suppress the normal error message that would occur
    when attempting to send a VOEvent when there are no broker connections.

-   Rearrange preliminary alert workflow so that sky map plots are generated
    for the newly added FITS file rather than an older FITS file that
    coincidentally has the same name.

-   Have ``gwcelery.detchar.check_vectors`` task apply all GraceDB log messages
    in order to increase robustness to recoverable GraceDB API errors.

-   Port over majority of P_astro code from gwcelery to the p-astro package.

-   Use cleaned data for parameter estimation.

-   The ``DQOK`` and ``DQV`` labels should be mutually exclusive. When
    ``gwcelery.tasks.detchar.check_vectors`` adds one of the ``DQOK`` or
    ``DQV`` labels, it will now first remove the other label.

-   Change exception in VOEevent parsing of Fermi subtreshold alerts to 
    match real incoming alerts.

-   Update Celery to 4.3.0.

0.5.6 (2018-05-08)
------------------

-   Extend the ``orchestrator_timeout`` to 300s and the ``pe_timeout`` to
    345s. The previous timeout was not sufficient for the online pipelines
    to upload all of their possible candidates, hence the extension.

0.5.5 (2019-05-03)
------------------

-   Cycle through llhoft, high latency frames, and low latency frames in
    detchar's cache creation.

-   Add explanations on options in online_pe.jinja2 for those who start
    parameter estimation based on the ini files uploaded to GraceDB.

-   Calculate horizon distance with psd.xml.gz to determine the upper limit of
    distance prior for parameter estimation.

-   Start parameter estimation when the lowest FAR of the events in a
    superevent is lower than the threshold.

-   Update the calibration uncertainties used for parameter estimation.

-   Handle an exception in VOEvent parsing of Fermi subthreshold alerts due to
    different param names.

-   Stop uploading corner plots of intrinsic parameters.

-   Connect to different GCN servers to receive alerts in the production and
    playground environments, because GCN does not support multiple receiver
    connections from the same client IP address to the same server.

-   Change the preferred event assignment logic to not let accidental candidates
    like G330298 which have low FAR but high SNR values to become the preferred
    event. From now on, ``superevents.should_publish`` takes maximum precedence
    for selecting the preferred event. The same is also used by orchestrator
    to expose events.

-   Update RAVEN coinc FAR task call which uses string params versus
    un-pickleable class object params.

-   Make sure to consume the entire response from every GraceDB API request.
    This will ensure that GraceDB API call has completed before the pipeline
    continues, and will fix errors like we encountered with S190426c where
    the pipeline would march along before uploads had finished.

-   Apply ADVREQ label earlier in the preliminary alert workflow.

-   Update LALSuite to version 6.54. We are now using a stable version again
    instead of a nightly build.

-   Add Nagios checks for GCN connectivity.

-   Improve uploaded comments so that it is easily understood which event has
    triggered parameter estimation.

0.5.4 (2019-05-01)
------------------

-   Provide a value for terrestrial count for P_astro for non-gstlal
    pipelines that is consistent with the FAR threshold used.

0.5.3 (2019-04-17)
------------------

-   Update ligo-followup-advocate to 0.0.28.

-   Stop using unreviewed cleaned data for parameter estimation.

-   Update detchar check to analyze full template duration for CBC events.

0.5.2 (2019-04-15)
------------------

-   Fix typo in ``gracedb.get_instruments``: there was the attribute lookup
    ``single.ifo``, which should have been the dictionary lookup
    ``single[ifo]``.

-   Fix ``gwcelery.tasks.p_astro_other.choose_snr`` for gstlal. This method did
    not previously expect to be called for gstlal, since it is typically only
    invoked for other pipelines. However, there is one case when ``choose_snr``
    is invoked for gstlal, which is when the ranking_data file from gstlal is
    corrupted with NaNs, causing P_astro for gstlal to fail. Thus, choose_snr
    has now been fixed to also handle gstlal as a pipeline.

0.5.1 (2019-04-12)
------------------

-   Changed default for em-bright from 2.83 to 3.0 M_sun to be consistent with
    notices.

0.5.0 (2019-04-12)
------------------

-   Give permissions to read the files under parameter estimation run
    directories to non-owner people so that rota people can check their
    progresses. The naming convention of the run directories changed.

-   EM-Bright ML classification requires review. Until then, give answer based
    on low-latency estimates.

-   Compute P_astro with mass-based template weighting. Template weights are
    now keyed on template parameters, rather than bin numbers. This should make
    P_astro immune to binning conventions.

-   Add form to manually send a preliminary GCN Notice.

-   Fix a typo in ``gwcelery.sub`` that caused the Flower dashboard to fail to
    start.

-   Round iDQ p(glitch) to 3 decimal places in GraceDB log message.

-   Switch log telemetry from the on-premise instance of Sentry at Caltech to a
    cloud-hosted subscription to sentry.io.

-   In the playground configuration, the ``gwcelery.tasks.gcn.validate`` task
    was producing false alarms because the GCN receiver was receiving VOEvents
    from the production instance, which would certainly differ in content from
    VOEvents in the playground instance. Fix this by having
    ``gwcelery.tasks.gcn.validate`` discard all VOEvents if the VOEvent
    broadcaster is disabled.

-   Update ligo-followup-advocate to 0.0.27.

-   Wait for 1 minute before parameter estimation in case the preferred event
    is updated with high latency.

-   Ensure that P_astro accounts for very loud MBTA and PyCBC events, whose FAR
    saturate at certain low values depending on instrument combination, but
    whose SNRs can increase indefinitely.

-   When a user triggers a Preliminary or Update alert through the Flask
    interface, create a GraceDB log message to record the username.

-   The Flask interface will now show a confirmation dialog before sending any
    alerts.

-   Add a terrifying warning to the Flask interface to make it clear that the
    interface is live.

0.4.3 (2019-04-05)
------------------

-   Now that LIGO/Virgo alerts are public, switch the GCN listener that we use
    to confirm receipt of our own GCN Notices from a managed, private
    connection to an anonymous, public connection.

-   Migrate the Flask and Flower dashboards from ldas-jobs.ligo.caltech.edu to
    emfollow.ligo.caltech.edu. The new URLs are:

    *   https://emfollow.ligo.caltech.edu/gwcelery
    *   https://emfollow.ligo.caltech.edu/flower
    *   https://emfollow.ligo.caltech.edu/playground/gwcelery
    *   https://emfollow.ligo.caltech.edu/playground/flower

    Remove the htaccess file from our public_html directory, since the reverse
    proxy configuration is now the responsibility of system administrators.

-   Display the GWCelery version number in the Flask application.

-   Add visualizations for ``p_astro.json`` source classification files.

0.4.2 (2019-04-05)
------------------

-   Calculation of number of instruments is now unified across superevent
    manager and orchestrator using gracedb method ``get_number_of_instruments``.

-   Enable automated preliminary alerts for all pipelines because disabling
    them in the orchestrator introduced some issues due to the criteria for
    releasing a public alert drifting away from the definition of a the
    preferred event of a superevent. We will instead trust pipelines that are
    still under review will upload events to the playground rather than the
    production environment.

0.4.1 (2019-04-02)
------------------

-   Fixed normalization issues with p_astro_gstlal.py; normalization
    was being applied in the wrong places during Bayes factor
    computation.

-   Require celery < 4.3.0 because that version breaks the nagios unit tests.

-   Update false alarm rate trials factors for preliminary alerts.

-   Enable sending GCN notices for fully automated preliminary alerts.

-   Add threshold_snr option in online_pe.jinja2, which is used to determine
    the upper limit of distance prior.

-   Use the same criteria to decide whether to expose an event publicly in
    GraceDB as we use to decide whether to issue a public alert.

-   Do not issue public alerts for single-instrument GW events.

-   Disable automated preliminary alerts for all pipelines but gstlal and cWB
    due to outstanding review items for the other pipelines.

0.4.0 (2019-03-29)
------------------

-   This is the penultimate release before LIGO/Virgo observing run 3 (O3).

-   Make detchar results easier to read by formatting as HTML table.

-   Allow iDQ to label DQV onto events based on p(glitch). Adjustable by
    pipeline.

-   Move functions in tasks/lalinference.py to lalinference_pipe.py in
    lalsuite.

-   Take into account calibration errors in automatic Parameter Estimation.

-   Do not use margphi option for automatic Parameter Estimation with ROQ
    waveform since that option is not compatible with ROQ likelihood.

-   Adjust WSGI middleware configuration to adapt to a change in Werkzeug
    0.15.0 that broke redirects on form submission in the Flask app. See
    https://github.com/pallets/werkzeug/pull/1303.

-   Use the new ``ligo.lw`` module for reading gstlal's
    ``ranking_data.psd.xml.gz`` files, because these files are now written
    using the new LIGO-LW format that uses integer row IDs.

-   Use clean data for parameter estimation.

-   Use production accounting group for PE runs on gracedb events.

-   Change threshold from log-likelihood equals 6 to a dynamic threshold that
    ensures that all gstlal events uploaded to gracedb get assigned a P_astro
    value.

0.3.1 (2019-03-18)
------------------

-   Fix a bug in translating keys from ``source_classification.json`` to
    keyword arguments for ``GraceDB.createVOEvent`` that caused VOEvents to
    be missing the ``HasNS`` and ``HasRemnant`` fields.

-   FAR threshold for sending preliminary notices for CBC is changed to
    1 per 2 months.

-   Upload log files when LALInference parameter estimation jobs fail or are
    aborted.

-   Changed the filename ``source_classification.json`` to ``em_bright.json``.

-   Change condor log directory from /var/tmp to ~/.cache/condor since gwcelery
    workers have separate /var/tmp when they are running as condor jobs and
    that causes problems when gwcelery tries to read log files.

-   Limit the maximum version of gwpy to 0.14.0 in order to work around a unit
    test failure that started with gwpy 0.14.1. See
    https://git.ligo.org/emfollow/gwcelery/issues/95.

-   Upload a diff whenever a LIGO/Virgo VOEvent that we receive from GCN does
    not match the original that we sent.

-   Wait for low-latency or high-latency frame files being transferred to the
    cluster before parameter estimation starts.

0.3.0 (2019-03-01)
------------------

-   Fixed exponent in the expression of foreground count in p_astro_other task.

-   Run the sky map postprocessing and add the ``PE_READY`` tag when
    LALInference finishes.

-   Include ``EM_COINC`` triggered circulars to upload to the superevent page.

-   p-astro reads mean values from a file on CIT, new mass-gap category
    added. Removed redundant functions from p_astro_gstlal module.

-   Continuous deployment on the Caltech cluster now uses a robot keytab and
    ``gsissh`` instead of SSH keys and vanilla ``ssh`` because the new
    my.ligo.org SSH key management does not support scripted access.

-   Improve the isolation between the production and playground instances of
    GWCelery by deploying them under two separate user accounts on the Caltech
    cluster.

-   Add functionality for em_bright task to query ``emfollow/data``
    for trained machine learning classifier and report probabilities
    based on it.

0.2.6 (2019-02-12)
------------------

-   Report an environment tag to Sentry corresponding to the GWCelery
    configuration module (``production``, ``test``, ``playground``, or
    ``development``) in order to differentiate log messages from different
    deployments.

-   The ``gwcelery condor`` command now identifies jobs that it owns by
    matching both the job batch name and the working directory. This makes it
    possible to run multiple isolated instances of GWCelery under HTCondor on
    the same cluster in different working directories.

-   Change the conditions for starting parameter estimation. For every CBC
    superevent, create an ``online_pe.ini`` file suitable for starting
    LALInference. However, only start LALInference if the false alarm rate is
    less than once per 2 weeks.

-   Determine PSD segment length for LALInference automatically based on data
    availability and data quality.

-   Add a Flask-based web interface for manually triggering certain tasks such
    as sending updated GCN notices.

0.2.5 (2019-02-01)
------------------

-   Pass along the GWCelery version number to Sentry.

-   Upload stdout and stderr when dag creation fails and notifications when
    submitted job fails in Parameter Estimation

-   Allow detchar module's ``create_cache`` to use gwdatafind when frames
    are no longer in llhoft.

-   The Nagios monitoring plugin will now report on the status of LVAlert
    subscriptions.

-   Change trials factor to 5 for both CBC and Burst categories. CBC includes
    the 4 CBC pipelines. Burst includes the 4 searches performed in total by
    the 2 Burst pipelines. An additional external coincidence search.

-   Automatically set up PE ini file depending on source parameters
    reported by detection pipelines.

0.2.4 (2018-12-17)
------------------

-   Fix broken links in log messages due to changes in GraceDB URL routes.

-   Whenever we send a public VOEvent using GCN, also make the corresponding
    VOEvent file in GraceDB public.

-   Don't include Mollweide projection PNG file in VOEvents. The sky map
    visualizations take longer to generate than the FITS files themselves, so
    they were unnecessarily slowing down the preliminary alerts.

-   Preliminary GCN FAR threshold is modified to be group (CBC, Burst, Test)
    specific.

0.2.3 (2018-12-16)
------------------

-   Update frame type used in LALInference Parameter Estimation.

-   Handle cases where ``p_astro_gstlal.compute_p_astro`` returns NaNs by
    falling back to ``p_astro_other.compute_p_astro``.

-   Fix a bug that prevented annotations that are specific to 3D sky maps from
    being performed for multi-resolution FITS files.

-   Fetch the graceid for the new event added from the gracedb logs
    since superevent packet does not provide information as to which
    event is added in case of type event_added.

0.2.2 (2018-12-14)
------------------

-   Add error handling for nonexistent iDQ frames in detchar module.

0.2.1 (2018-12-14)
------------------

-   Update detchar module configuration for ER13.

0.2.0 (2018-12-14)
------------------

-   This is the release of GWCelery for ER13.

-   Run two separate instances of Comet, one to act as a broker and one to act
    as a client. This breaks a cycle that would cause retransmission of GRB
    notices back to GCN.

-   Fix a race condition that could cause preliminary alerts to be sent out for
    events for which data quality checks had failed.

-   Unpin the ``redis`` package version because recent updates to Kombu and
    Billiard seem to have fixed the Nagios unit tests.

-   Start the Comet VOEvent broker as a subprocess intead of using
    ``multiprocessing`` and go back to using PyGCN instead of Comet as the
    VOEvent client. This is a workaround for suspected instability due to a bad
    interaction between ``redis-py`` and ``multiprocessing``.

-   Reset Matplotlib's style before running ``ligo-skymap-plot`` and
    ``ligo-skymap-plot-volume``. There is some other module (probably in
    LALSuite) that is messing with the rcparams at module scope, which was
    causing Mollweide plots to come out with unusual aspect ratios.

-   Run ``check_vectors`` upon addition of an event to a superevent if the
    superevent already has an ``DQV`` label.

-   Do not check the DMT-DQ_VECTOR for pipelines which use gated h(t).

-   Remove static example VOEvents from the Open Alert Users Guide. We never
    used them because activating sample alerts got help until ER13.

-   Disable running the Orchestrator for test events for ER13. After ER13 is
    over, we need to carefully audit the code and make sure that test events
    are handled appropriately.

-   Enable public GraceDB entries and public GCNs for mock (MDC) events. For
    **real** events in ER13, disable public preliminary GCNs. Instead, advocate
    signoffs will trigger making events and GCN notices public: ``ADVOK`` for
    initial notices and ``ADVNO`` for retraction notices.

-   Include source classification output (BNS/NSBH/BBH/Terrestrial) in GCN
    Notices.

0.1.7 (2018-11-27)
------------------

-   Pin the ``redis`` package version at <3 because the latest version of redis
    breaks the Nagios unit tests.

-   Ditch our own homebrew VOEvent broker and use Comet instead.

-   In addition to traditional flat, fixed-nside sky maps, BAYESTAR will now
    also upload an experimental multiresolution format described in
    `LIGO-G1800186-v4 <https://dcc.ligo.org/LIGO-G1800186-v4/public>`_.

0.1.6 (2018-11-14)
------------------

-   Update URL for static example event.

0.1.5 (2018-11-13)
------------------

-   Add tasks for submitting HTCondor DAGs.

-   Add a new module, ``gwcelery.tasks.lalinference``, which provides tasks to
    start parameter estimation with LALInference and upload the results to
    GraceDB.

-   Depend on lalsuite nightly build from 2018-11-04 to pick up changes to
    LALInference for Python 3 support.

-   Send static example VOEvents from the Open Alert Users Guide.
    This will provide a stream of example alerts for astronomers until GraceDB
    is ready for public access.

-   Add trials factor correction to the event FAR when comparing against
    FAR threshold to send out preliminary GCN.

-   Require that LIGO/Virgo VOEvents that we receive from GCN match the
    original VOEvents from GraceDB byte-for-byte, since GCN will now pass
    through our VOEvents without modification.

0.1.4 (2018-10-29)
------------------

-   Work around a bug in astropy.visualization.wcsaxes that affected all-sky
    plots when Matplotlib's ``text.usetex`` rcparam is set to ``True``
    (https://github.com/astropy/astropy/issues/8004). This bug has evidently
    been present since at least astropy 1.3, but was not being triggered until
    recently: it is likely that some other package that we import
    (e.g. lalsuite) is now globally setting ``text.usetex`` to ``True``.

-   A try except is added around updateSuperevent to handle a bad
    request error from server side when updating superevent parameters
    which have nearby values.

-   Send automatic preliminary alerts only for events with a false alarm rate
    below a maximum value specified by a new configuration variable,
    ``preliminary_alert_far_threshold``.

-   State vector vetoes will not suppress processing of preliminary sky maps
    and source classification. They will still suppress sending preliminary
    alerts.

-   Set ``open_alert`` to ``True`` for all automated VOEvents.

0.1.3 (2018-10-26)
------------------

-   Preliminary GCN is not sent for superevents created from offline gw events.

-   Add ``dqr_json`` function to ``gwcelery.tasks.detchar``, which uploads a 
    DQR-compatible json to GraceDB with the results of the detchar checks.

-   Depend on ligo.skymap >= 0.0.17.

-   Fix a bug in sending initial, update, and retraction GCN notices: we were
    sending the VOEvent filenames instead of the file contents.

0.1.2 (2018-10-11)
------------------

-   Setted ``vetted`` flag to true for all initial, update, and retraction
    alerts that are triggered by GraceDB signoffs.

-   Write GraceDB signoffs, instead of just labels, to simulate initial and
    retraction alerts for mock events, because merely creating the ``ADVNO``
    or ``ADVOK`` label does not cause GraceDB to erase the ``ADVREQ`` label.
    This change makes mock alerts more realistic.

-   Change filename of cWB sky maps from ``skyprobcc_cWB.fits`` to
    ``cWB.fits.gz`` for consistency with other pipelines.

-   Any time that we send a VOEvent, first change the GraceDB permissions on
    the corresponding superevent so that it is visible to the public. Note that
    this has no effect during the ongoing software engineering runs because
    LVEM and unauthenticated access are currently disabled in GraceDB.

0.1.1 (2018-10-04)
------------------

-   Use the ``public`` tag instead of the ``lvem`` tag to mark preliminary sky
    maps for public access rather than LV-EM partner access. Note that GraceDB
    has not yet actually implemented unauthenticated access, so this should
    have no effect during our ongoing software engineering runs.

-   Add ``check_idq`` function to detchar module, which reads probabilities
    generated by iDQ.

-   Automated ``DQV`` labels should not trigger retraction notices because they
    prevent preliminary notices from being sent in the first place.

-   The criterion for selecting a superevent's preferred event now prefers
    multiple-detector events to single-detector events, with precedence over
    source type (CBC versus burst). Any remaining tie is broken by using SNR
    for CBC and FAR for Burst triggers.

-   By default, initial and update alerts will find and send the most recently
    added public sky map.

-   The initial and update sky maps no longer perform sky map annotations,
    because they would only be duplicating the annotations performed as part
    of the preliminary alert.

-   Mock events now include example initial and retraction notices. Two minutes
    after each mock event is uploaded, there will be either an ``ADVOK`` or an
    ``ADVNO`` label applied at random, triggering either an initial or a
    retraction notice respectively.

-   Depend on ligo-gracedb >= 2.0.1 in order to pull in a bug fix for VOEvents
    with ProbHasNS or ProbHasRemnant set to 0.0.

-   Use the ``sentry-sdk`` package instead of the deprecated ``raven`` package
    for Sentry integration.

0.1.0 (2018-09-26)
------------------

-   Separated the external GCN listening handlers into two: one that listens
    to GCNs about SNEWS triggers and another that listens to Fermi and Swift.

-   Fixed calls to the raven temporal coincidence search so that search results
    separate SNEWS triggers from Fermi and Swift.

-   Add space-time FAR calculation for GRB and GW superevent coincidences.
    This only runs when skymaps from both triggers are available to download.

-   Add human vetting for initial GCN notices. For each new superevent that
    passes state vector checks, the ``ADVREQ`` label is applied. Rapid response
    team users should set their GraceDB notification preferences to alert
    them on ``ADVREQ`` labels. If a user sets the ``ADVOK`` label, then an
    initial notice is issued. If a user sets the ``ADVNO`` label, then a
    retraction notice is issued.

-   Update the LVAlert host for gracedb-playground.ligo.org.

-   Add experimental integration with `Sentry <https://sentry.io/>`_ for log
    aggregation and error reporting.

-   Track API and LVAlert schema changes in ligo-gracedb 2.0.0.

0.0.31 (2018-09-04)
-------------------

-   Refactor external trigger handling to separate it from the orchestrator.

-   Fixed a bug in the VOEvent broker to only issue "iamalive" messages after
    sending the first VOEvent.

-   Pass group argument to set time windows appropriately when performing raven
    coincidence searches. Search in the [-600, 60]s range and [-5, 1]s range
    around external triggers for Burst events and CBC events respectively.
    Similarly, search in the [-60, 600]s and [-1, 5]s range around Burst and
    CBC events for external triggers.

-   Compute and upload FAR for GRB external trigger/superevent coincidence upon
    receipt of the EM_COINC label application to a superevent.

-   Add continuous integration testing for Python 3.7, and run test suite
    against all supported Python versions (3.6, 3.7).

-   Update ligo.skymap to 0.0.15.

0.0.30 (2018-08-02)
-------------------

-   Manage superevents for production, test, and MDC events separately.

-   Add some more validation of LIGO/Virgo VOEvents from GCN.

-   Remove now-unused task ``gwcelery.tasks.orchestartor.continue_if``.

-   Add ``check_vectors`` run for external triggers.

-   Change the preferred event selection criteria for burst events
    to be FAR instead of SNR.

-   Add ``gwcelery nagios`` subcommand for Nagios monitoring.

-   Incorporate Virgo DQ veto streams into ``check_vectors``

-   Update ligo-raven to 1.3 and ligo-followup-advocate to 0.0.11.

0.0.29 (2018-07-31)
-------------------

-   Add a workflow graph to superevents module documentation.

-   Add ``gwcelery condor resubmit`` as a shortcut for
    ``gwcelery condor rm; gwcelery condor submit``.

-   Fix deprecation warning due to renaming of
    ``ligo.gracedb.rest.Gracedb.createTag`` to
    ``ligo.gracedb.rest.Gracedb.addTag``.

-   Update ligo-gracedb to 2.0.0.dev1.

0.0.28 (2018-07-25)
-------------------

-   Add injection checks to ``check_vector``.

-   Bitmasks are now defined symbolically in ``detchar``.

-   Refactor configuration so that it is possible to customize settings
    through an environment variable.

0.0.27 (2018-07-22)
-------------------

-   The preferred event for superevents is now decided based on higher SNR
    value instead of lower FAR in the case of a tie between groups.

-   A check for the existence of the gstlal trigger database is performed
    so that compute_p_astro does not return None.

0.0.26 (2018-07-20)
-------------------

-   Fix spelling of the label that is applied to events after p_astro finishes,
    changed from ``P_ASTRO_READY`` to ``PASTRO_READY``.

-   Run p_astro calculation for mock events.

-   Overhaul preliminary alert pipeline so that it is mostly feature complete
    for both CBC and Burst events, and uses a common code path for both types.
    Sky map annotations now occur for both CBC and Burst localizations.

-   Switch to using the pre-registered port 8096 for receiving proprietary
    LIGO/Virgo alerts on emfollow.ligo.caltech.edu. This means that the
    capability to receive GCNs requires setting up a site configuration in
    advance with Scott Barthelmey.

    Once we switch to sending public alerts exclusively, then we can switch
    back to using port 8099 for anonymous access, requiring no prior site
    configuration.

0.0.25 (2018-07-19)
-------------------

-   Reintroduce pipeline-dependent pre/post peeks for ``check_vector`` after
    fixing issue where pipeline information was being looked for in the wrong
    dictionary.

-   ``check_vector`` checks all detectors regardless of instruments used, but
    only appends labels based on active instruments.

-   Fix a few issues in the GCN broker:

    *   Decrease the frequency of keepalive ("iamalive" in VOEvent Transport
        Protocol parlance) packets from once a second to once a minute at the
        request of Scott Barthelmey.

    *   Fix a possible race condition that might have caused queued VOEvents to
        be thrown away unsent shortly after a scheduled keepalive packet.

    *   Consume and ignore all keepalive and ack packets from the client so
        that the receive buffer does not overrun.

-   Add ``p_astro`` computation for ``gstlal`` pipeline. The copmutation is
    launched for all cbc_gstlal triggers.

0.0.24 (2018-07-18)
-------------------

-   Revert pipeline-dependent pre/post peeks for ``check_vector`` because they
    introduced a regression: it caused the orchestrator failed without running
    any annotations.

0.0.23 (2018-07-18)
-------------------

-   Add timeout and keepalive messages to GCN broker.

-   Update ligo-gracedb to 2.0.0.dev0 and ligo.skymap to 0.0.12.

-   Add superevent duration for gstlal-spiir pipeline.

-   Fix fallback for determining superevent duration for unknown pipelines.

-   Make ``check_vector`` pre/post peeks pipeline dependent.

0.0.22 (2018-07-11)
-------------------

-   Process gstlal-spiir events.

-   Create combined LVC-Fermi skymap in case of coincident triggers and
    upload to GraceDB superevent page. Also upload the original external
    trigger sky map to the external trigger GraceDB page.

-   Generalize conditional processing of complex canvases by replacing the
    ``continue_if_group_is()`` task with a more general task that can be used
    like ``continue_if(group='CBC')``.

-   Add a ``check_vector_prepost`` configuration variable to control how much
    padding is added around an event for querying the state vector time series.

    This should have the beneficial side effect of fixing some crashes for
    burst events, for which the bare duration of the superevent segment was
    less than one sample.

0.0.21 (2018-07-10)
-------------------

-   MBTA events in GraceDB leave the ``search`` field blank. Work around this
    in ``gwcelery.tasks.detchar.check_vectors`` where we expected the field
    to be present.

-   Track change in GraceDB JSON response for VOEvent creation.

0.0.20 (2018-07-09)
-------------------

-   After fixing some minor bugs in code that had not yet been tested live,
    sending VOEvents to GCN now works.

0.0.19 (2018-07-09)
-------------------

-   Rewrite the GCN broker so that it does not require a dedicated worker.

-   Send VOEvents for preliminary alerts to GCN.

-   Only perform state vector checks for detectors that were online,
    according to the preferred event.

-   Exclude mock data challenge events from state vector checks.

0.0.18 (2018-07-06)
-------------------

-   Add detector state vector checks to the preliminary alert workflow.

0.0.17 (2018-07-05)
-------------------

-   Undo accidental configuration change in last version.

0.0.16 (2018-07-05)
-------------------

-   Stop listening for three unnecessary GCN notice types:
    ``SWIFT_BAT_ALARM_LONG``, ``SWIFT_BAT_ALARM_SHORT``, and
    ``SWIFT_BAT_KNOWN_SRC``.

-   Switch to `SleekXMPP <http://sleekxmpp.com>`_ for the LVAlert client,
    instead of `PyXMPP2 <http://jajcus.github.io/pyxmpp2/>`_. Because SleekXMPP
    has first-class support for publish-subscribe, the LVAlert listener can
    now automatically subscribe to all LVAlert nodes for which our code has
    handlers. Most of the client code now lives in a new external package,
    `sleek-lvalert <https://git.ligo.org/emfollow/sleek-lvalert>`_.

0.0.15 (2018-06-29)
-------------------

-   Change superevent threshold and mock event rate to once per hour.

-   Add ``gracedb.create_label`` task.

-   Always upload external triggers to the 'External' group.

-   Add rudimentary burst event workflow to orchestrator: it just generates
    VOEvents and circulars.

-   Create a label in GraceDB whenever ``em_bright`` or ``bayestar`` completes.

0.0.14 (2018-06-28)
-------------------

-   Fix typo that was causing a task to fail.

-   Decrease orchestrator timeout to 15 seconds.

0.0.13 (2018-06-28)
-------------------

-   Change FAR threshold for creation of superevents to 1 per day.

-   Update ligo-followup-advocate to >= 0.0.10. Re-enable automatic generation
    of GCN circulars.

-   Add "EM bright" classification. This is rudimentary and based only on the
    point mass estimates from the search pipeline because some of the EM bright
    classifier's dependencies are not yet ready for Python 3.

-   Added logic to select CBC events as preferred event over Burst. FAR acts
    as tie breaker when groups for preferred event and new event match.

-   BAYESTAR now adds GraceDB URLs of events to FITS headers.

0.0.12 (2018-06-28)
-------------------

-   Prevent receiving duplicate copies of LVAlert messages by unregistering
    redundant LVAlert message types.

-   Update to ligo-followup-advocate >= 0.0.9 to update GCN Circular text for
    superevents. Unfortunately, circulars are still disabled due to a
    regression in ligo-gracedb (see
    https://git.ligo.org/lscsoft/gracedb-client/issues/7).

-   Upload BAYESTAR sky maps and annotations to superevents.

-   Create (but do not send) preliminary VOEvents for all superevents.
    No vetting is performed yet.

0.0.11 (2018-06-27)
-------------------

-   Submit handler tasks to Celery as a single group.

-   Retry GraceDB tasks that raise a ``TimeoutError`` exception.

-   The superevent handler now skips LVAlert messages that do not affect
    the false alarm rate of an event (e.g. simple log messages).

    (Note that the false alarm rate in GraceDB is set by the initial event
    upload and can be updated by replacing the event; however replacing the
    event does not produce an LVAlert message at all, so there is no way to
    intercept it.)

-   Added a query kwarg to superevents method to reduce latency in
    fetching the superevents from gracedb.

-   Refactored getting event information for update type events so
    that gracedb is polled only once to get the information needed
    for superevent manager.

-   Renamed the ``set_preferred_event`` task in gracedb.py to
    ``update_superevent`` to be a full wrapper around the ``updateSuperevent``
    client function. Now it can be used to set preferred event and also update
    superevent time windows.

-   Many ``cwb`` (extra) attributes, which should be floating point
    numbers, are present in lvalert packet as strings. Casting them
    to avoid embarassing TypeErrors.

-   Reverted back the typecasting of far, gpstime into float. This is
    fixed in https://git.ligo.org/lscsoft/gracedb/issues/10

-   CBC ``t_start`` and ``t_end`` values are changed to 1 sec interval.

-   Added ligo-raven to run on external trigger and superevent creation
    lvalerts to search for coincidences. In case of coincidence, EM_COINC label
    is applied to the superevent and external trigger page and the external
    trigger is added to the list of em_events in superevent object dictionary.

-   ``cwb`` and ``lib`` nodes added to superevent handler.

-   Events are treated as finite segment window, initial superevent
    creation with preferred event window. Addition of events to
    superevents may change the superevent window and also the
    preferred event.

-   Change default GraceDB server to https://gracedb-playground.ligo.org/
    for open public alert challenge.

-   Update to ligo-gracedb >= 1.29dev1.

-   Rename the ``get_superevent`` task to ``get_superevents`` and add
    a new ``get_superevent`` task that is a trivial wrapper around
    ``ligo.gracedb.rest.GraceDb.superevent()``.

0.0.10 (2018-06-13)
-------------------

-   Model the time extent of events and superevents using the
    ``glue.segments`` module.

-   Replace GraceDB.get with GraceDB.superevents from the recent dev
    release of gracedb-client.

-   Fix possible false positive matches between GCNs for unrelated GRBs
    by matching on both TrigID (which is generally the mission elapsed time)
    and mission name.

-   Add the configuration variable ``superevent_far_threshold`` to limit
    the maximum false alarm rate of events that are included in superevents.

-   LVAlert handlers are now passed the actual alert data structure rather than
    the JSON text, so handlers are no longer responsible for calling
    ``json.loads``. It is a little bit more convenient and possibly also faster
    for Celery to deserialize the alert messages.

-   Introduce ``Production``, ``Development``, ``Test``, and ``Playground``
    application configuration objects in order to facilitate quickly switching
    between GraceDB servers.

-   Pipeline specific start and end times for superevent segments. These values
    are controlled via configuration variables.

0.0.9 (2018-06-06)
------------------

-   Add missing LVAlert message types to superevent handler.

0.0.8 (2018-06-06)
------------------

-   Add some logging to the GCN and LVAlert dispatch code in order to
    diagnose missed messages.

0.0.7 (2018-05-31)
------------------

-   Ingest Swift, Fermi, and SNEWS GCN notices and save them in GraceDB.

-   Depend on the pre-release version of the GraceDB client, ligo-gracedb
    1.29.dev0, because this is the only version that supports superevents at
    the moment.

0.0.6 (2018-05-26)
------------------

-   Generate GCN Circular drafts using `ligo-followup-advocate
    <https://git.ligo.org/emfollow/ligo-followup-advocate>`_.

-   In the continuous integration pipeline, validate PEP8 naming conventions
    using `pep8-naming <https://pypi.org/project/pep8-naming/>`_.

-   Add instructions for measuring test coverage and running the linter locally
    to the contributing guide.

-   Rename ``gwcelery.tasks.voevent`` to ``gwcelery.tasks.gcn`` to make it
    clear that this submodule contains functionality related to GCN notices,
    rather than VOEvents in general.

-   Rename ``gwcelery.tasks.dispatch`` to ``gwcelery.tasks.orchestrator`` to
    make it clear that this module encapsulates the behavior associated with
    the "orchestrator" in the O3 low-latency design document.

-   Mock up calls to BAYESTAR in test suite to speed it up.

-   Unify dispatch of LVAlert and GCN messages using decorators.
    GCN notice handlers are declared like this::

        import lxml.etree
        from gwcelery.tasks import gcn

        @gcn.handler(gcn.NoticeType.FERMI_GBM_GND_POS,
                     gcn.NoticeType.FERMI_GBM_FIN_POS)
        def handle_fermi(payload):
            root = lxml.etree.fromstring(payload)
            # do work here...

    LVAlert message handlers are declared like this::

        import json
        from gwcelery.tasks import lvalert

        @lvalert.handler('cbc_gstlal',
                         'cbc_pycbc',
                         'cbc_mbta')
        def handle_cbc(alert_content):
            alert = json.loads(alert_content)
            # do work here...

-   Instead of carrying around the GraceDB service URL in tasks, store the
    GraceDB host name in the Celery application config.

-   Create superevents by simple clustering in time. Currently this is only
    supported by the ``gracedb-dev1`` host.

0.0.5 (2018-05-08)
------------------

-   Disable socket access during most unit tests. This adds some extra
    assurance that we don't accidentally interact with production servers
    during the unit tests.

-   Ignore BAYESTAR jobs that raise a ``DetectorDisabled`` error. These
    exceptions are used for control flow and do not constitute a real error.
    Ignoring these jobs avoids polluting logs and the Flower monitor.

0.0.4 (2018-04-28)
------------------

-   FITS history and comment entries are now displayed in a monospaced font.

-   Adjust error reporting for some tasks.

-   Depend on newer version of ``ligo.skymap``.

-   Add unit tests for the ``gwcelery condor submit`` subcommand.

0.0.3 (2018-04-27)
------------------

-   Fix some compatibility issues between the ``gwcelery condor submit``
    subcommand and the format of ``condor_q -totals -xml`` with older versions
    of HTCondor.

0.0.2 (2018-04-27)
------------------

-   Add ``gwcelery condor submit`` and related subcommands as shortcuts for
    managing GWCelery running under HTCondor.

0.0.1 (2018-04-27)
------------------

-   This is the initial release. It provides rapid sky localization with
    BAYESTAR, sky map annotation, and sending mock alerts.

-   By default, GWCelery is configured to listen to the test LVAlert server.

-   Sending VOEvents to GCN/TAN is disabled for now.
