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
app = Celery(__name__, backend='redis://', broker='redis://')

# Only run these tests if a Redis server is running.
try:
    app.connection().ensure_connection(max_retries=1)
except OperationalError:
    pytestmark = pytest.mark.skip('No Redis server is running.')


@app.task(base=EternalTask, bind=True, ignore_result=True)
def example_task_aborts_gracefully(self):
    while not self.is_aborted():
        sleep(0.1)


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
    sleep(1)
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


@pytest.fixture
def start_test_app_worker(tmpdir):
    """Start up a worker for the test app."""
    argv = ['celery', 'worker', '-B', '-c', '5',
            '-s', str(tmpdir / 'celerybeat-schedule'),
            '-l', 'debug']
    p = Process(target=app.start, args=(argv,))
    p.start()
    yield
    p.terminate()
    p.join()


def test_eternal(start_test_app_worker):
    """Test worker with two eternal tasks: one that always succeeds,
    and one that always fails."""
    assert example_task_canary.delay().get()
