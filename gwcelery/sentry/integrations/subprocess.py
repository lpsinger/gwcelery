from subprocess import CalledProcessError

from sentry_sdk.integrations import Integration
from sentry_sdk.scope import add_global_event_processor


class SubprocessIntegration(Integration):
    """Capture stderr and stdout from CalledProcessError exceptions."""

    identifier = 'subprocess'

    @staticmethod
    def setup_once():

        @add_global_event_processor
        def capture(event, hint):
            if 'exc_info' not in hint:
                return event

            _, e, _ = hint['exc_info']
            if not isinstance(e, CalledProcessError):
                return event

            breadcrumbs = event.get('breadcrumbs')
            if not breadcrumbs:
                return event

            data = breadcrumbs[-1].setdefault('data', {})
            for key in ['stderr', 'stdout']:
                value = getattr(e, key)
                data[key] = value.decode(errors='replace')

            return event
