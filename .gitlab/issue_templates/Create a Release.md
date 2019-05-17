**Git ref:** <!-- insert git reference -->

# Checklist

## Basics

1.  [ ] Has the CI pipeline succeeded, including all unit tests and code quality checks?
2.  [ ] Does CHANGES.rst list all significant changes since the last release? Is it free from spelling and grammatical errors?

## Playground deployment

3.  [ ] Has the playground deployment run for at least 10 minutes?
4.  [ ] Is the playground deployment connected to LVAlert?
5.  [ ] Is the playground deployment connected to GCN?
6.  [ ] Has the playground deployment produced an MDC superevent?
7.  [ ] Does the MDC superevent have the following annotations?
    - [ ] bayestar.multiorder.fits
    - [ ] bayestar.fits.gz
    - [ ] bayestar.png
    - [ ] bayestar.volume.png
    - [ ] bayestar.html
    - [ ] p_astro.json
    - [ ] p_astro.png
    - [ ] em_bright.json

/label ~Release
