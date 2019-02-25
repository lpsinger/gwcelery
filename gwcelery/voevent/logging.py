"""Integration between the Celery, Twisted, and Comet logging systems."""

from celery.signals import after_setup_logger
from celery.utils.log import get_logger
import comet.log
from twisted.python.log import PythonLoggingObserver

log = get_logger(__name__)

__all__ = ('after_setup_logger', 'log')


@after_setup_logger.connect
def after_setup_logger(logger, loglevel, **kwargs):
    """Celery :doc:`signal handler <celery:userguide/signals>` to set up
    capturing of all log messages from Comet and Twisted.

    * Celery uses the Python standard library's :mod:`logging` module. Twisted
      has its own separate logging facility. Use Twisted's
      :class:`~twisted.python.log.PythonLoggingObserver` to forward all Twisted
      log messages to the Python :mod:`logging` module.

    * Comet uses the Twisted logging facility, but has its own separate
      management of log severity level (e.g., *info*, *debug*). Set Comet's log
      level to match Celery's.
    """
    comet.log.LEVEL = 10 * loglevel
    PythonLoggingObserver(logger.name).start()
