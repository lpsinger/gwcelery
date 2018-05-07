from celery import Celery

# Celery application object.
# Use pickle serializer, because it supports byte values.
# Use redis broker, because it supports locks (and thus singleton tasks).
app = Celery(
    'gwcelery', broker='redis://',
    config_source=dict(
        accept_content=['json', 'pickle'],
        event_serializer='json',
        result_serializer='pickle',
        task_serializer='pickle',
        lvalert_host='lvalert-test.cgca.uwm.edu',
        gracedb_host='gracedb-dev1.ligo.org',
        gcn_bind_address='',
        gcn_bind_port=5341,
        gcn_remote_address='128.183.96.236',  # capella2.gsfc.nasa.gov
        superevent_d_t_start=10.0,
        superevent_d_t_end=10.0
    )
)

# Use the same URL for both the result backend and the broker.
app.conf['result_backend'] = app.conf.broker_url
