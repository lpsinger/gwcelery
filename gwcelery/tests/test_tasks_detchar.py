from unittest.mock import patch
from pkg_resources import resource_filename

from gwpy.timeseries import TimeSeries

from ..tasks import detchar


channel = 'DMT-DQ_VECTOR'
ifo = 'H1'
start = 1214714160
end = 1214714164


@patch('gwcelery.tasks.detchar.read_gwf',
       return_value=TimeSeries.read(
           resource_filename(__name__, 'data/check_vector_test_pass.gwf'),
           'H1:DMT-DQ_VECTOR'))
def test_check_vector(mock_read_gwf):
    assert detchar.check_vector(ifo, channel, start, end, 0b11, 'any')

    assert not detchar.check_vector(ifo, channel, start, end,
                                    0b1111, 'any')
