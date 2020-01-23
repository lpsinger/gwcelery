import os
import sys
from unittest.mock import Mock

from ..tools.condor_submit_helper import main


def test_condor_submit_helper(monkeypatch, tmpdir):

    # Create a fake machine ClassAd filename.
    filename = str(tmpdir / 'classad')
    with open(filename, 'w') as f:
        # "This mission is too important for me to allow you to jeopardize it."
        print('ClientMachine = "hal9000.discovery"', file=f)
        # "Open the pod bay doors, HAL."
        print('RemoteUser = "david.bowman"', file=f)
        # "I know that you and Frank were planning to disconnect me,
        # and I'm afraid that's something I cannot allow to happen."
        print('Activity = killing', file=f)

    monkeypatch.setenv('_CONDOR_MACHINE_AD', filename)
    monkeypatch.setenv('CELERY_BROKER_URL', '')
    mock_execvp = Mock()
    monkeypatch.setattr(sys, 'argv', ['condor_submit_helper', 'foo', 'bar'])
    monkeypatch.setattr(os, 'execvp', mock_execvp)

    main()

    assert os.environ['CELERY_BROKER_URL'] == 'redis://hal9000.discovery'
    mock_execvp.assert_called_once_with('foo', ['foo', 'bar'])
