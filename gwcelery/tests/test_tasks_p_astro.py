from unittest.mock import patch

from ..tasks import p_astro


@patch('gwcelery.tasks.gracedb.download.run',
       return_value='{"Terrestrial": 0.001, "BNS": 0.65, "NSBH": 0.20, '
                    '"MassGap": 0.10, "BBH": 0.059}')
@patch('gwcelery.tasks.gracedb.upload.run')
def test_handle(mock_upload, mock_download):
    alert = {
        'alert_type': 'log',
        'data': {'filename': 'p_astro.json'},
        'uid': 'S1234'
    }
    p_astro.handle(alert)
    mock_download.assert_called_once_with('p_astro.json', 'S1234')
    mock_upload.assert_called_once()
