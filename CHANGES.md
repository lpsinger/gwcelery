# Changelog

## 0.0.6 (unreleased)

- Generate GCN Circular drafts using ``ligo-followup-advocate``.

- In the continuous integration pipeline, validate PEP8 naming conventions
  using [``pep8-naming``](https://pypi.org/project/pep8-naming/).

- Add instructions for measuring test coverage and running the linter locally
  to the contributing guide.

## 0.0.5 (2018-05-08)

- Disable socket access during most unit tests. This adds some extra assurance
  that we don't accidentally interact with production servers during the unit
  tests.

- Ignore BAYESTAR jobs that raise a ``DetectorDisabled`` error. These
  exceptions are used for control flow and do not constitute a real error.
  Ignoring these jobs avoids polluting logs and the Flower monitor.

## 0.0.4 (2017-04-28)

- FITS history and comment entries are now displayed in a monospaced font.

- Adjust error reporting for some tasks.

- Depend on newer version of ``ligo.skymap``.

- Add unit tests for the ``gwcelery condor submit`` subcommand.

## 0.0.3 (2017-04-27)

- Fix some compatibility issues between the ``gwcelery condor submit``
  subcommand and the format of ``condor_q -totals -xml`` with older versions
  of HTCondor.

## 0.0.2 (2017-04-27)

- Add `gwcelery condor submit` and related subcommands as shortcuts for
  managing GWCelery running under HTCondor.

## 0.0.1 (2017-04-27)

- This is the initial release. It provides rapid sky localization with
  BAYESTAR, sky map annotation, and sending mock alerts.

- By default, GWCelery is configured to listen to the test LVAlert server.

- Sending VOEvents to GCN/TAN is disabled for now.
