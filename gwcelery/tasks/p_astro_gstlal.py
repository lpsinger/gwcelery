"""Computation of `p_astro` by source category.
   See Kapadia et al (2019), arXiv:1903.06881, for details.
"""
import json
from os.path import basename
import shutil
import tempfile
from urllib import error, request

from celery.utils.log import get_task_logger
import h5py
from ligo import p_astro_gstlal_utils as gstlal
from ligo import p_astro_computation as pastrocomp
import numpy as np

from ..import app
from ..util import PromiseProxy

from . import p_astro_other

log = get_task_logger(__name__)


def _get_activation_counts_hf():
    try:
        with tempfile.NamedTemporaryFile() as f:
            response = request.urlopen(app.conf['p_astro_weights_url'])
            try:
                shutil.copyfileobj(response, f)
                f.flush()
            finally:
                response.close()
            return h5py.File(f.name, 'r')
    except (ValueError, error.URLError):
        return None


_activation_counts_hf = PromiseProxy(_get_activation_counts_hf)


@app.task(shared=False)
def compute_p_astro(files):
    """
    Task to compute `p_astro` by source category.

    Parameters
    ----------
    files : tuple
        Tuple of byte content from (coinc.xml, ranking_data.xml.gz)

    Returns
    -------
    p_astros : str
        JSON dump of the p_astro by source category

    Example
    -------
    >>> p_astros = json.loads(compute_p_astro(files))
    >>> p_astros
    {'BNS': 0.999, 'BBH': 0.0, 'NSBH': 0.0, 'Terrestrial': 0.001}
    """
    coinc_bytes, ranking_data_bytes = files

    # Acquire information pertaining to the event from coinc.xml
    # uploaded to GraceDB
    log.info(
        'Fetching event data from coinc.xml')
    event_ln_likelihood_ratio, event_mass1, event_mass2, \
        event_spin1z, event_spin2z, snr, far = \
        gstlal._get_event_ln_likelihood_ratio_svd_endtime_mass(coinc_bytes)

    # Using the zerolag log likelihood ratio value event,
    # and the foreground/background model information provided
    # in ranking_data.xml.gz, compute the ln(f/b) value for this event
    zerolag_ln_likelihood_ratios = np.array([event_ln_likelihood_ratio])
    log.info('Computing f_over_b from ranking_data.xml.gz')
    try:
        livetime = app.conf['p_astro_livetime']
        ln_f_over_b, lam_0 = \
            gstlal._get_ln_f_over_b(ranking_data_bytes,
                                    zerolag_ln_likelihood_ratios,
                                    livetime,
                                    extinct_zerowise_elems=40)
    except ValueError:
        log.exception("NaN encountered, using approximate method ...")
        pipeline = "gstlal"
        instruments = None
        return p_astro_other.compute_p_astro(snr,
                                             far,
                                             event_mass1,
                                             event_mass2,
                                             pipeline,
                                             instruments)

    # Read mean values from url file
    mean_values_dict = p_astro_other.read_mean_values()
    mean_values_dict["counts_Terrestrial"] = lam_0

    # Get the number of bins
    filename = basename(app.conf['p_astro_weights_url'])
    num_bins = int(filename.split("-")[2].split("_")[1])

    # Compute categorical p_astro values
    p_astro_values = \
        pastrocomp.evaluate_p_astro_from_bayesfac(np.exp(ln_f_over_b[0]),
                                                  mean_values_dict,
                                                  event_mass1,
                                                  event_mass2,
                                                  event_spin1z,
                                                  event_spin2z,
                                                  num_bins,
                                                  _activation_counts_hf)

    # Dump values in json file
    return json.dumps(p_astro_values)
