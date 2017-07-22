import pkg_resources
try:
    from unittest.mock import patch
except ImportError:
    from mock import patch

import pytest

from ..tasks.dispatch import dispatch


@patch('gwcelery.tasks.dispatch.bayestar', autospec=True)
def test_dispatch_psd(mock_bayestar):
    """Test dispatch of an LVAlert message for a PSD upload."""
    # Test LVAlert payload.
    payload = pkg_resources.resource_string(__name__, 'data/lvalert_psd.json')

    # Run function under test
    dispatch(payload)

    # Check that the correct actions were dispatched.
    mock_bayestar.assert_called_once_with(
        'T250822', 'https://gracedb-test.ligo.org/api/')