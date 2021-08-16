from unittest import mock

import pytest

from .. import main
from ..tools import condor


@pytest.mark.parametrize('subcommand,extra_args', [['rm', ()],
                                                   ['hold', ()],
                                                   ['release', ()],
                                                   ['q', ('-nobatch',)]])
@mock.patch('os.execvp', side_effect=SystemExit(0))
def test_condor_subcommand(mock_execvp, subcommand, extra_args):
    """Test all trivial Condor subcommands."""
    try:
        main(['gwcelery', 'condor', subcommand])
    except SystemExit as e:
        assert e.code == 0

    cmd = 'condor_' + subcommand
    mock_execvp.assert_called_once_with(
        cmd, (cmd, *extra_args, *condor.get_constraints()))


@mock.patch('subprocess.check_output', return_value=b'<classads></classads>')
@mock.patch('os.execvp', side_effect=SystemExit(0))
def test_condor_submit_not_yet_running(mock_execvp, mock_check_output):
    """Test starting the Condor job."""
    try:
        main(['gwcelery', 'condor', 'submit'])
    except SystemExit as e:
        assert e.code == 0

    mock_check_output.assert_called_once_with(
        ('condor_q', '-xml', *condor.get_constraints()))
    mock_execvp.assert_called_once_with(
        'condor_submit', ('condor_submit',
                          'accounting_group=ligo.dev.o3.cbc.pe.bayestar',
                          condor.SUBMIT_FILE))


@mock.patch('subprocess.check_output',
            return_value=b'<classads><c></c></classads>')
@mock.patch('os.execvp', side_effect=SystemExit(0))
def test_condor_submit_already_running(mock_execvp, mock_check_output):
    """Test that we don't start the condor jobs if they are already running."""
    try:
        main(['gwcelery', 'condor', 'submit'])
    except SystemExit as e:
        assert e.code == 1

    mock_check_output.assert_called_once_with(
        ('condor_q', '-xml', *condor.get_constraints()))
    mock_execvp.assert_not_called()


class MockMonotonic:
    """Mock :meth:`time.monotonic` to speed up the apparent passage of time."""

    def __init__(self):
        self._t = 0.0

    def __call__(self):
        self._t += 1.0
        return self._t


@mock.patch('time.sleep')
@mock.patch('time.monotonic', new_callable=MockMonotonic)
@mock.patch('subprocess.check_output',
            return_value=b'<classads><c></c></classads>')
@mock.patch('subprocess.check_call')
def test_condor_resubmit_fail(mock_check_call, _, __, ___):
    """Test that ``gwcelery condor resubmit`` fails if we are unable to
    ``condor_rm`` the jobs.
    """
    try:
        main(['gwcelery', 'condor', 'resubmit'])
    except SystemExit as e:
        assert e.code == 1
    mock_check_call.assert_called_with(
        ('condor_rm', *condor.get_constraints()))


@mock.patch('subprocess.check_output',
            return_value=b'<classads></classads>')
@mock.patch('subprocess.check_call')
@mock.patch('os.execvp', side_effect=SystemExit(0))
def test_condor_resubmit_succeeds(mock_execvp, mock_check_call, _):
    """Test that ``gwcelery condor resubmit`` fails if we are unable to
    ``condor_rm`` the jobs.
    """
    try:
        main(['gwcelery', 'condor', 'resubmit'])
    except SystemExit as e:
        assert e.code == 0
    mock_check_call.assert_not_called()
    mock_execvp.assert_called_once_with(
        'condor_submit', ('condor_submit',
                          'accounting_group=ligo.dev.o3.cbc.pe.bayestar',
                          condor.SUBMIT_FILE))
