"""Flask web application for manually triggering certain tasks."""

import argparse
import os

from celery.bin.base import Command
import click
import click.testing
from flask.cli import FlaskGroup

from ..flask import app
from .. import views as _  # noqa: F401


@click.group(cls=FlaskGroup, create_app=lambda *args, **kwargs: app)
def main():
    pass


class FlaskCommand(Command):

    def add_arguments(self, parser):
        # Capture command line help from Flask
        runner = click.testing.CliRunner()
        result = runner.invoke(main, ['--help'])
        flask_help = result.output.replace('main', 'gwcelery flask')

        group = parser.add_argument_group(
            'Flask Options', description=flask_help)
        group.add_argument(
            'flask_args', nargs=argparse.REMAINDER, help=argparse.SUPPRESS)

    def run(self, *args, flask_args=(), **kwargs):
        # Allow port number to be specified from an environment variable.
        port = os.environ.get('FLASK_PORT')
        if port:
            flask_args += ['--port', port]
        main(flask_args)


main.__doc__ = FlaskCommand.__doc__ = __doc__
