"""Flask web application for manually triggering certain tasks."""
from contextlib import ExitStack, nullcontext

from celery.bin.base import CeleryDaemonCommand, CeleryOption, LOG_LEVEL
from celery.platforms import detached
import click
from flask.cli import FlaskGroup

from ..flask import app
from .. import views as _  # noqa: F401


class CeleryDaemonFlaskGroup(FlaskGroup):

    def __init__(self, *args, **kwargs):
        super().__init__(self, *args, **kwargs)
        self.params.extend(CeleryDaemonCommand(name='flask').params)


def maybe_detached(*, detach, **kwargs):
    return detached(**kwargs) if detach else nullcontext()


@click.group(cls=CeleryDaemonFlaskGroup, help=__doc__,
             context_settings={'auto_envvar_prefix': 'FLASK'})
@click.option('-D',
              '--detach',
              cls=CeleryOption,
              is_flag=True,
              default=False,
              help="Start as a background process.")
@click.option('-l',
              '--loglevel',
              default='WARNING',
              cls=CeleryOption,
              type=LOG_LEVEL,
              help="Logging level.")
@click.pass_context
def flask(ctx, detach=None, loglevel=None, logfile=None,
          pidfile=None, uid=None, gid=None, umask=None, **kwargs):
    # Look up Celery app
    celery_app = ctx.parent.obj.app

    # # Prepare to pass Flask app to Flask CLI
    ctx.obj.create_app = lambda *args, **kwargs: app

    # Detach from the tty if requested.
    # FIXME: After we update to click >= 8, replace the elaborate construction
    # below with ctx.with_resource(maybe_detached(...))
    exit_stack = ExitStack()
    ctx.call_on_close(exit_stack.close)
    exit_stack.enter_context(maybe_detached(detach=detach,
                                            logfile=logfile, pidfile=pidfile,
                                            uid=uid, gid=gid, umask=umask))

    celery_app.log.setup(loglevel, logfile)
