from celery import bootsteps, signals
from celery.contrib import abortable
from celery.utils.log import get_task_logger
from ..celery_singleton import clear_locks, Singleton

# Logging
log = get_task_logger(__name__)


@signals.beat_init.connect
def beat_init(sender, **kwargs):
    clear_locks(sender.app)


class AbortStep(bootsteps.StartStopStep):
    """Boot step to abort all tasks on shutdown."""
    requires = {'celery.worker.components:Pool'}

    def stop(self, worker):
        for request in worker.state.active_requests:
            abortable.AbortableAsyncResult(request.task_id).abort()


class EternalTask(abortable.AbortableTask, Singleton):
    """Base class for a task that should run forever, and should be restarted
    if it ever exits. The task should periodically check `self.is_aborted()`
    and exit gracefully if it is set. During a warm shutdown, we will attempt
    to abort the task."""

    @classmethod
    def on_bound(cls, app):
        app.add_periodic_task(1.0, cls)
        app.steps['worker'].add(AbortStep)

    def __exit_message(self):
        if self.is_aborted():
            log.info('Eternal process exited early due to abort')
        else:
            log.error('Eternal process exited early!')

    def on_failure(self, *args, **kwargs):
        super(EternalTask, self).on_failure(*args, **kwargs)
        self.__exit_message()

    def on_success(self, *args, **kwargs):
        super(EternalTask, self).on_success(*args, **kwargs)
        self.__exit_message()
