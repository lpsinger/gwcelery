from requests.exceptions import HTTPError
from sentry_sdk.integrations import Integration
from sentry_sdk.scope import add_global_event_processor


class RequestsIntegration(Integration):
    """Sentry integration to capture detail about HTTP errors from requests."""

    identifier = 'requests'

    @staticmethod
    def setup_once():

        @add_global_event_processor
        def capture(event, hint):
            if 'exc_info' not in hint:
                return event

            _, e, _ = hint['exc_info']
            if not isinstance(e, HTTPError):
                return event

            breadcrumbs = event.get('breadcrumbs')
            if not breadcrumbs:
                return event

            data = breadcrumbs[-1].setdefault('data', {})
            data['response'] = e.response.text

            return event
