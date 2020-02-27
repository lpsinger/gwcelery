import os

from sentry_sdk.api import configure_scope
from sentry_sdk.integrations import Integration


def _read_classad(filename):
    with open(filename) as f:
        for line in f:
            key, _, value = line.partition('=')
            key = key.strip()
            value = value.strip().strip('"')
            yield key, value


class CondorIntegration(Integration):
    """Custom Sentry integration to report the HTCondor job ID."""

    identifier = 'condor'

    @staticmethod
    def setup_once():
        try:
            data = dict(_read_classad(os.environ['_CONDOR_JOB_AD']))
        except (KeyError, IOError):
            pass
        else:
            with configure_scope() as scope:
                scope.set_tag('htcondor.cluster_id', '{}.{}'.format(
                    data['ClusterId'], data['ProcId']))
