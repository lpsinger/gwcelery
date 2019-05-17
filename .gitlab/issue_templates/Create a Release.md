**Git ref:** <!-- insert git reference -->

# Checklist

## Basics

1.  [ ] The CI pipeline succeeded, including all unit tests and code quality checks.
2.  [ ] [CHANGES.rst](CHANGES.rst) lists all significant changes since the last release. It is free from spelling and grammatical errors.

## Playground deployment

3.  [ ] The playground deployment run for at least 10 minutes.
4.  [ ] The [Flower monitor](https://emfollow.ligo.caltech.edu/playground/flower) is reachable and shows no unexpected task failures.
5.  [ ] The [Flask dashboard](https://emfollow.ligo.caltech.edu/playground/gwcelery) is reachable.
6.  [ ] The playground deployment is connected to LVAlert.
7.  [ ] The playground deployment is connected to GCN (receiving only).

## Mock events

8.  [ ] The playground deployment has [produced an MDC superevent](https://gracedb-playground.ligo.org/latest/?query=MDC&query_type=S).
9.  [ ] The MDC superevent has the following annotations.
    - [ ] `bayestar.multiorder.fits`
    - [ ] `bayestar.fits.gz`
    - [ ] `bayestar.png`
    - [ ] `bayestar.volume.png`
    - [ ] `bayestar.html`
    - [ ] `p_astro.json`
    - [ ] `p_astro.png`
    - [ ] `em_bright.json`
10. [ ] The MDC superevent has the following labels.
    - [ ] `EMBRIGHT_READY`
    - [ ] `GCN_PRELIM_SENT`
    - [ ] `PASTRO_READY`
    - [ ] `SKYMAP_READY`
11. [ ] The MDC superevent has a preliminary VOEvent.
12. [ ] The MDC superevent has either an `ADVOK` or an `ADVNO` label.
13. [ ] Issuing an `ADVOK` signoff through GraceDB results in an initial VOEvent.
14. [ ] Issuing an `ADVNO` signoff through GraceDB results in a retraction VOEvent.
15. [ ] Requesting an update alert through the [Flask dashboard](https://emfollow.ligo.caltech.edu/playground/gwcelery) results in an update VOEvent.

/label ~Release
