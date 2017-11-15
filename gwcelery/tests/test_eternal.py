from __future__ import absolute_import
from multiprocessing import Process
from time import sleep

from celery import Celery
from celery.signals import worker_process_shutdown
from pytest_cov.embed import multiprocessing_finish

from ..util import EternalTask

# Celery application object.
# Use redis backend, because it supports locks (and thus singleton tasks).
app = Celery('gwcelery.tests.test_eternal',
             backend='redis://', broker='redis://')


@app.task(base=EternalTask, ignore_result=True)
def example_task_always_succeeds():
    sleep(0.1)


@app.task(base=EternalTask, ignore_result=True)
def example_task_always_fails():
    sleep(0.1)
    raise RuntimeError('Expected to fail!')


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
    sleep(2)
    p.terminate()
    p.join()
