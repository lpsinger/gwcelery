**Git ref**: *insert git reference here*

# Checklist

## Basics

1.  [ ] The CI pipeline succeeded, including all unit tests and code quality checks. *place link to pipeline here*
2.  [ ] [CHANGES.rst](CHANGES.rst) lists all significant changes since the last release. It is free from spelling and grammatical errors.
3.  [ ] The [latest Readthedocs documentation build](https://readthedocs.org/projects/gwcelery/builds/) passed and the [latest docs](https://gwcelery.readthedocs.io/en/latest/) are correctly rendered. Autodoc-generated API docs for tasks are shown.
4.  [ ] If there is [milestone](https://git.ligo.org/emfollow/gwcelery/-/milestones) for this
    release, then the list of issues and merge requests that have been
    addressed is accurate. Any unaddressed issues and merge requests have been
    moved to another milestone.

## Playground deployment

4.  [ ] Sentry does not show any new [unresolved issues on playground](https://sentry.io/organizations/ligo-caltech/issues/?environment=playground&groupStatsPeriod=14d&project=1425216&query=is%3Aunresolved&statsPeriod=14d) that indicate new bugs or regressions.
5.  [ ] The playground deployment has run for at least 10 minutes.
6.  [ ] The [Flower monitor](https://emfollow-playground.ligo.caltech.edu/flower) is reachable and shows no unexpected task failures.
7.  [ ] The [Flask dashboard](https://emfollow-playground.ligo.caltech.edu/gwcelery) is reachable.
8.  [ ] The playground deployment is connected to LVAlert (in Flower, find the main gwcelery-worker, click Other, and look at the list of subscribed LVAlert nodes).
9.  [ ] The playground deployment is connected to GCN.

## Mock events

10. [ ] The playground deployment has [produced an MDC superevent](https://gracedb-playground.ligo.org/latest/?query=MDC&query_type=S).
11. [ ] The MDC superevent has the following annotations.
    - [ ] `bayestar.multiorder.fits`
    - [ ] `bayestar.fits.gz`
    - [ ] `bayestar.png`
    - [ ] `bayestar.volume.png`
    - [ ] `bayestar.html`
    - [ ] `p_astro.json`
    - [ ] `p_astro.png`
    - [ ] `em_bright.json`
    - [ ] `em_bright.png`
12. [ ] The MDC superevent has the following labels.
    - [ ] `EMBRIGHT_READY`
    - [ ] `GCN_PRELIM_SENT`
    - [ ] `PASTRO_READY`
    - [ ] `SKYMAP_READY`
13. [ ] The MDC superevent has two automatic preliminary VOEvents, JSON packets, and Avro packets if `GCN_PRELIM_SENT` is applied.
    - [ ] 2 preliminary VOEvents
    - [ ] 2 preliminary JSON packets
    - [ ] 2 preliminary Avro packets
14. [ ] Issuing a manual preliminary alert from the [Flask dashboard](https://emfollow-playground.ligo.caltech.edu/gwcelery) sends another preliminary alert.
    - [ ] The alert **is sent** successfully if `ADVOK` or an `ADVNO` label is **not applied** this time.
    - [ ] Alternatively, a preliminary alert is **blocked** due to presence of `ADVOK` or `ADVNO`.
15. [ ] The MDC superevent has either an `ADVOK` or an `ADVNO` label.
16. [ ] Issuing an `ADVOK` signoff through GraceDB results in an initial VOEvent.
17. [ ] Issuing an `ADVNO` signoff through GraceDB results in a retraction VOEvent.
18. [ ] Requesting an update alert through the [Flask dashboard](https://emfollow-playground.ligo.caltech.edu/gwcelery) results in an update VOEvent.
19. [ ] Playground has recently [produced an MDC superevent with an external coincidence](https://gracedb-playground.ligo.org/latest/?query=MDC+EM_COINC&query_type=S), i.e. with a `EM_COINC` label. Use the [Flask dashboard](https://emfollow-playground.ligo.caltech.edu/gwcelery) to do this manually (note that joint events with Swift may not pass publishing conditions).
20. [ ] The joint MDC superevent has the following annotations.
    - [ ] `coincidence_far.json`
    - [ ] `bayestar-ext.fits.gz` or `subthreshold.bayestar-ext.fits.gz`
    - [ ] `bayestar-ext.png` or `subthreshold.bayestar-ext.png`
21. [ ] The joint MDC superevent has the following labels.
    - [ ] `EM_COINC`
    - [ ] `RAVEN_ALERT`
    - [ ] `GCN_PRELIM_SENT`
22. [ ] The joint MDC superevent is sending alerts with coincidence information.
    - [ ] At least one VOEvent with `<Group name="External Coincidence">`.
    - [ ] At least one circular w/ `-emcoinc-` in filename.

## Replay events

23. [ ] [A Production superevent labeled `GCN_PRELIM_SENT`](https://gracedb-playground.ligo.org/latest/?query=Production+GCN_PRELIM_SENT&query_type=S&get_neighbors=&results_format=) has the following parameter estimation annotations and the `PE_READY` label.
    - [ ] `online_bilby_pe.ini`
    - [ ] `Bilby.posterior_samples.hdf5`
    - [ ] `Bilby.multiorder.fits`
    - [ ] `Bilby.html`
    - [ ] `Bilby.fits.gz`
    - [ ] `Bilby.png`
    - [ ] `Bilby.volume.png`
    - [ ] `Bilby.extrinsic.png`
    - [ ] `Bilby.intrinsic.png`
    - [ ] `PE_READY`

/label ~Release
