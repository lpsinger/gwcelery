"""Integration between the Celery, Twisted, and Comet logging systems."""
from celery.signals import after_setup_logger
from celery.utils.log import get_logger
import comet.log
from twisted.python.log import PythonLoggingObserver

log = get_logger(__name__)

__all__ = ('log',)


@after_setup_logger.connect
def after_setup_logger(logger, loglevel, **kwargs):
    # Comet has a separate log level setting.
    # Match it to the Celery log level.
    comet.log.LEVEL = 10 * loglevel
    # Hook Twisted into the Python standard library :mod:`logging` system
    # so that Twisted log messages are captured by Celery and Sentry.
    PythonLoggingObserver(logger.name).start()
