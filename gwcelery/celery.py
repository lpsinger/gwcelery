from __future__ import absolute_import

from celery import Celery

# Celery application object.
# Use pickle serializer, because it supports byte values.
app = Celery('gwcelery', backend='redis://', broker='redis://',
    config_source=dict(
        accept_content=['json', 'pickle'],
        event_serializer='json',
        result_serializer='pickle',
        task_serializer='pickle'
    )
)
