# Changelog

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
