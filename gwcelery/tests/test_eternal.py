from __future__ import absolute_import
from multiprocessing import Process
from time import sleep

from celery import Celery
from celery.signals import worker_process_shutdown
from kombu.exceptions import OperationalError
import pytest

from ..util import EternalTask

# Celery application object.
# Use redis backend, because it supports locks (and thus singleton tasks).
app = Celery('gwcelery.tests.test_eternal',
             backend='redis://', broker='redis://')

# Only run these tests if a Redis server is running.
try:
    app.connection().ensure_connection(max_retries=1)
except OperationalError:
    pytestmark = pytest.mark.skip('No Redis server is running.')



@app.task(base=EternalTask, ignore_result=True)
def example_task_always_succeeds():
    sleep(0.1)


@app.task(base=EternalTask, ignore_result=True)
def example_task_always_fails():
    sleep(0.1)
    raise RuntimeError('Expected to fail!')


@app.task
def example_task_canary():
    """A simple task that, when finished, will tell us that the server
    has been running for a while."""
    sleep(3)
    return True


# Only needed if we are measuring test coverage
try:
    from pytest_cov.embed import multiprocessing_finish
except ImportError:
    pass
else:
    @worker_process_shutdown.connect
    def worker_process_shutdown(*args, **kwargs):
        multiprocessing_finish()


def test_eternal(tmpdir):
    """Test worker with two eternal tasks: one that always succeeds,
    and one that always fails."""
    argv = ['celery', 'worker', '-B',
            '-s', str(tmpdir / 'celerybeat-schedule'),
            '-l', 'info']
    p = Process(target=app.start, args=(argv,))
    p.start()
    assert example_task_canary.delay().get()
    p.terminate()
    p.join()
