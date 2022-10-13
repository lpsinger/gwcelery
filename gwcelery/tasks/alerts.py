import json

from astropy import time
from celery import group
from celery.utils.log import get_logger
from hop.models import AvroBlob

from ..import app
from . import gracedb

log = get_logger(__name__)


def _create_base_alert_dict(classification, superevent, alert_type,
                            raven_coinc=False):
    '''Create the base of the alert dictionary, with all contents except the
    skymap and the external coinc information.'''
    # NOTE Everything that comes through this code path will be marked as
    # public. However, MDC events with this flag are not made public on
    # GraceDB-playground and GraceDB-test.
    # Re time_created: Dont need better than second precision for alert times
    alert_dict = {
        'alert_type': alert_type.upper(),
        'time_created': time.Time.now().utc.iso.split('.')[0],
        'superevent_id': superevent['superevent_id'],
        'urls': {'gracedb': superevent['links']['self'].replace('api/', '') +
                 'view/'},
        'event': None,
        'external_coinc': None
    }

    if alert_type == 'retraction':
        return alert_dict

    if classification and classification[0] is not None:
        properties = json.loads(classification[0])
    else:
        properties = {}

    if classification and classification[1] is not None:
        classification = json.loads(classification[1])
    else:
        classification = {}

    alert_dict['event'] = {
        'time': time.Time(superevent['t_0'], format='gps').utc.iso,
        'far': superevent['far'],
        'instruments': sorted(
            superevent['preferred_event_data']['instruments'].split(',')
        ),
        'group': superevent['preferred_event_data']['group'],
        'pipeline': superevent['preferred_event_data']['pipeline'],
        'search': superevent['preferred_event_data']['search'],
        'properties': properties,
        'classification': classification
    }

    return alert_dict


@gracedb.task(shared=False)
def _add_external_coinc_to_alert(alert_dict, superevent):
    external_event = gracedb.get_event(superevent['em_type'])

    alert_dict['external_coinc'] = {
        'gcn_notice_id':
            external_event['extra_attributes']['GRB']['trigger_id'],
        'ivorn': external_event['extra_attributes']['GRB']['ivorn'],
        'observatory': external_event['pipeline'],
        'search': external_event['search'],
        'time_difference': round(superevent['t_0']
                                 - external_event['gpstime'], 2),
        'time_coincidence_far': superevent['time_coinc_far'],
        'time_sky_position_coincidence_far': superevent['space_coinc_far']
    }

    return alert_dict


@app.task(bind=True, shared=False, queue='kafka', ignore_result=True)
def _upload_notice(self, payload, brokerhost, superevent_id):
    '''
    Upload serialized alert notice to GraceDB
    '''
    config = self.app.conf['kafka_alert_config'][brokerhost]
    kafka_writer = self.app.conf['kafka_streams'][brokerhost]

    # FIXME Drop get_payload_input method once
    # https://github.com/scimma/hop-client/pull/190 is merged
    alert_dict = kafka_writer.get_payload_input(payload)
    message = 'Kafka alert notice sent to {}'.format(config['url'])

    filename = '{}-{}.{}'.format(
        alert_dict['superevent_id'],
        alert_dict['alert_type'].lower(),
        config['suffix']
    )

    gracedb.upload.delay(payload.serialize()['content'], filename,
                         superevent_id, message, tags=['public', 'em_follow'])


@app.task(bind=True, queue='kafka', shared=False)
def _send(self, alert_dict, skymap, brokerhost):
    """Write the alert to the Kafka topic"""
    # Copy the alert dictionary so we dont modify the original
    payload_dict = alert_dict.copy()
    # Add skymap to alert_dict
    config = self.app.conf['kafka_alert_config'][brokerhost]
    if alert_dict['event'] is not None:
        # dict.copy is a shallow copy, so need to copy event dict as well since
        # we plan to modify it
        payload_dict['event'] = alert_dict['event'].copy()

        # Encode the skymap
        encoder = config['skymap_encoder']
        payload_dict['event']['skymap'] = encoder(skymap)

    # Write to kafka topic
    serialization_model = \
        self.app.conf['kafka_streams'][brokerhost].serialization_model
    # FIXME Drop logic that packs payload_dict in a list once
    # https://github.com/scimma/hop-client/pull/190 is merged
    payload = serialization_model(
            [payload_dict] if serialization_model is AvroBlob else
            payload_dict)
    self.app.conf['kafka_streams'][brokerhost].write(payload)

    return payload


@app.task(bind=True, ignore_result=True, queue='kafka', shared=False)
def send(self, skymap_and_classification, superevent, alert_type,
         raven_coinc=False):
    """Send an public alert to all currently connected kafka brokers.

    Parameters
    ----------
    skymap_and_classification : tuple, None
        The filecontents of the skymap followed by a collection of JSON
        strings. The former generated by
        :meth:`gwcelery.tasks.gracedb.download`, the latter generated by
        :meth:`gwcelery.tasks.em_bright.classifier` and
        :meth:`gwcelery.tasks.p_astro.compute_p_astro` or content of
        ``p_astro.json`` uploaded by gstlal respectively. Can also be None.
    superevent : dict
        The superevent dictionary, typically obtained from an IGWN Alert or
        from querying GraceDB.
    alert_type : {'earlywarning', 'preliminary', 'initial', 'update'}
        The alert type.
    raven_coinc: bool
        Is there a coincident external event processed by RAVEN?

    """

    if skymap_and_classification is not None:
        skymap, *classification = skymap_and_classification
    else:
        skymap = None
        classification = None

    alert_dict = _create_base_alert_dict(
        classification,
        superevent,
        alert_type,
        raven_coinc=raven_coinc
    )

    if raven_coinc and alert_type != 'retraction':
        canvas = (
            _add_external_coinc_to_alert.s(alert_dict, superevent)
            |
            group(
                (
                    _send.s(skymap, brokerhost)
                    |
                    _upload_notice.s(brokerhost, superevent['superevent_id'])
                ) for brokerhost in self.app.conf['kafka_streams'].keys()
            )
        )
    else:
        canvas = (
            group(
                (
                    _send.s(alert_dict, skymap, brokerhost)
                    |
                    _upload_notice.s(brokerhost, superevent['superevent_id'])
                ) for brokerhost in self.app.conf['kafka_streams'].keys()
            )
        )

    canvas.apply_async()


@app.task(shared=False)
def _create_skymap_classification_tuple(skymap, classification):
    return (skymap, *classification)


@app.task(shared=False, ignore_result=True)
def download_skymap_and_send_alert(classification, superevent, alert_type,
                                   skymap_filename=None, raven_coinc=False):
    """Wrapper for send function when caller has not already downloaded the
    skymap.

    Parameters
    ----------
    classification : tuple, None
        A collection of JSON strings, generated by
        :meth:`gwcelery.tasks.em_bright.classifier` and
        :meth:`gwcelery.tasks.p_astro.compute_p_astro` or
        content of ``p_astro.json`` uploaded by gstlal respectively;
        or None
    superevent : dict
        The superevent dictionary, typically obtained from an IGWN Alert or
        from querying GraceDB.
    alert_type : {'earlywarning', 'preliminary', 'initial', 'update'}
        The alert type.
    skymap_filename : string
        The skymap filename.
    raven_coinc: bool
        Is there a coincident external event processed by RAVEN?

    """

    if skymap_filename is not None and alert_type != 'retraction':
        canvas = (
            gracedb.download.si(
                skymap_filename,
                superevent['superevent_id']
            )
            |
            _create_skymap_classification_tuple.s(classification)
            |
            send.s(superevent, alert_type, raven_coinc=raven_coinc)
        )
    else:
        canvas = send.s(
            (None, classification),
            superevent,
            alert_type,
            raven_coinc=raven_coinc
        )

    canvas.apply_async()
