"""Application configuration for ``gracedb.ligo.org``. Inherits all settings
from :mod:`gwcelery.conf.playground`, with the exceptions below."""

from . import *  # noqa: F401, F403

lvalert_host = 'lvalert.cgca.uwm.edu'
"""LVAlert host."""

gracedb_host = 'gracedb.ligo.org'
"""GraceDb host."""

voevent_broadcaster_address = ':5341'
"""The VOEvent broker will bind to this address to send GCNs.
This should be a string of the form `host:port`. If `host` is empty,
then listen on all available interfaces."""

voevent_broadcaster_whitelist = ['capella2.gsfc.nasa.gov']
"""List of hosts from which the broker will accept connections.
If empty, then completely disable the broker's broadcast capability."""

voevent_receiver_address = '68.169.57.253:8096'
"""The VOEvent listener will connect to this address to receive GCNs.
If empty, then completely disable the GCN listener.

We are temporarily using the pre-registered port 8096 for receiving
proprietary LIGO/Virgo alerts on emfollow.ligo.caltech.edu. This means that
the capability to receive GCNs requires setting up a site configuration in
advance with Scott Barthelmey.

Once we switch to sending public alerts exclusively, then we can switch
back to using port 8099 for anonymous access, requiring no prior site
configuration."""

llhoft_glob = '/dev/shm/kafka/{detector}/*.gwf'
"""File glob for low-latency h(t) frames."""

low_latency_frame_types = {'H1': 'H1_llhoft',
                           'L1': 'L1_llhoft',
                           'V1': 'V1_llhoft'}
"""Types of frames used in Parameter Estimation with LALInference (see
:mod:`gwcelery.tasks.lalinference`)"""

high_latency_frame_types = {'H1': 'H1_HOFT_C00',
                            'L1': 'L1_HOFT_C00',
                            'V1': 'V1Online'}
"""Types of nonllhoft-frames used in Parameter Estimation with LALInference
(see :mod:`gwcelery.tasks.lalinference`)"""

strain_channel_names = {'H1': 'H1:GDS-CALIB_STRAIN_CLEAN',
                        'L1': 'L1:GDS-CALIB_STRAIN_CLEAN',
                        'V1': 'V1:Hrec_hoft_16384Hz'}
"""Names of h(t) channels used in Parameter Estimation with LALInference (see
:mod:`gwcelery.tasks.lalinference`)"""

sentry_environment = 'production'
"""Record this `environment tag
<https://docs.sentry.io/enriching-error-data/environments/>`)` in Sentry log
messages."""
