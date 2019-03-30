"""Module containing the computation of p_astro by source category
   See https://dcc.ligo.org/LIGO-T1800072 for details.
"""
import io
import json

from celery.utils.log import get_task_logger
from glue.ligolw.ligolw import LIGOLWContentHandler \
    as GlueLIGOLWContentHandler
from glue.ligolw import array as glue_ligolw_array
from glue.ligolw import param as glue_ligolw_param
from glue.ligolw import utils as glue_ligolw_utils
from glue.ligolw import lsctables as glue_lsctables
from ligo.lw import ligolw
from ligo.lw.ligolw import LIGOLWContentHandler
from ligo.lw import array as ligolw_array
from ligo.lw import param as ligolw_param
from ligo.lw import utils as ligolw_utils
from ligo.lw import lsctables
from lal import rate
import numpy as np

from ..import app

from . import p_astro_other

log = get_task_logger(__name__)

# adapted from gstlal far.py RankingStatPDF


class _RankingStatPDF(object):
    ligo_lw_name_suffix = "gstlal_inspiral_rankingstatpdf"

    @classmethod
    def from_xml(cls, xml, name):
        """
        Find the root of the XML tree containing the
        serialization of this object
        """
        xml, = [elem for elem in
                xml.getElementsByTagName(ligolw.LIGO_LW.tagName)
                if elem.hasAttribute("Name") and
                elem.Name == "%s:%s" % (name, cls.ligo_lw_name_suffix)]
        # create a uninitialized instance
        self = super().__new__(cls)
        # populate from XML
        self.noise_lr_lnpdf = rate.BinnedLnPDF.from_xml(xml, "noise_lr_lnpdf")
        self.signal_lr_lnpdf = rate.BinnedLnPDF.from_xml(xml,
                                                         "signal_lr_lnpdf")
        self.zero_lag_lr_lnpdf = rate.BinnedLnPDF.from_xml(
            xml, "zero_lag_lr_lnpdf")
        return self


def _parse_likelihood_control_doc(xmldoc):
    name = "gstlal_inspiral_likelihood"
    rankingstatpdf = _RankingStatPDF.from_xml(xmldoc, name)
    if rankingstatpdf is None:
        raise ValueError("document does not contain likelihood ratio data")
    return rankingstatpdf


@ligolw_array.use_in
@ligolw_param.use_in
@lsctables.use_in
class _ContentHandler(LIGOLWContentHandler):
    pass


@glue_ligolw_array.use_in
@glue_ligolw_param.use_in
@glue_lsctables.use_in
class _GlueContentHandler(GlueLIGOLWContentHandler):
    pass


def _get_ln_f_over_b(ranking_data_bytes, ln_likelihood_ratios):
    ranking_data_xmldoc = ligolw_utils.load_fileobj(
        io.BytesIO(ranking_data_bytes), contenthandler=_ContentHandler)
    rankingstatpdf = _parse_likelihood_control_doc(ranking_data_xmldoc)
    # affect the zeroing of the PDFs below threshold by hacking the
    # histograms. Do the indexing ourselves to not 0 the bin @ threshold
    noise_lr_lnpdf = rankingstatpdf.noise_lr_lnpdf
    signal_lr_lnpdf = rankingstatpdf.signal_lr_lnpdf
    zero_lag_lr_lnpdf = rankingstatpdf.zero_lag_lr_lnpdf
    ssorted = zero_lag_lr_lnpdf.array.cumsum()[-1] - 10000
    idx = zero_lag_lr_lnpdf.array.cumsum().searchsorted(ssorted)

    ln_likelihood_ratio_threshold = \
        zero_lag_lr_lnpdf.bins[0].lower()[idx]

    rankingstatpdf.noise_lr_lnpdf.array[
        :noise_lr_lnpdf.bins[0][ln_likelihood_ratio_threshold]] \
        = 0.
    rankingstatpdf.noise_lr_lnpdf.normalize()

    rankingstatpdf.signal_lr_lnpdf.array[
        :signal_lr_lnpdf.bins[0][ln_likelihood_ratio_threshold]] \
        = 0.
    rankingstatpdf.signal_lr_lnpdf.normalize()

    rankingstatpdf.zero_lag_lr_lnpdf.array[
        :zero_lag_lr_lnpdf.bins[0][ln_likelihood_ratio_threshold]] \
        = 0.
    rankingstatpdf.zero_lag_lr_lnpdf.normalize()

    f = rankingstatpdf.signal_lr_lnpdf
    b = rankingstatpdf.noise_lr_lnpdf
    ln_f_over_b = \
        np.array([f[ln_lr, ] - b[ln_lr, ] for ln_lr in ln_likelihood_ratios])
    if np.isnan(ln_f_over_b).any():
        raise ValueError("NaN encountered in ranking statistic PDF ratios")
    if np.isinf(np.exp(ln_f_over_b)).any():
        raise ValueError(
            "infinity encountered in ranking statistic PDF ratios")
    return ln_f_over_b


def _get_event_ln_likelihood_ratio_svd_endtime_mass(coinc_bytes):
    coinc_xmldoc, _ = glue_ligolw_utils.load_fileobj(
        io.BytesIO(coinc_bytes), contenthandler=_GlueContentHandler)
    coinc_event, = glue_lsctables.CoincTable.get_table(coinc_xmldoc)
    coinc_inspiral, = glue_lsctables.CoincInspiralTable.get_table(coinc_xmldoc)
    sngl_inspiral = glue_lsctables.SnglInspiralTable.get_table(coinc_xmldoc)

    assert all([sngl_inspiral[i].Gamma0 == sngl_inspiral[i+1].Gamma0
                for i in range(len(sngl_inspiral)-1)]), \
        "svd bank different between ifos!"
    return (coinc_event.likelihood,
            coinc_inspiral.end_time,
            coinc_inspiral.mass,
            sngl_inspiral[0].mass1,
            sngl_inspiral[0].mass2,
            coinc_inspiral.snr,
            coinc_inspiral.combined_far)


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
        'Fetching ln_likelihood_ratio, svd bin, endtime, mass from coinc.xml')
    event_ln_likelihood_ratio, event_endtime, \
        event_mass, event_mass1, event_mass2, snr, far = \
        _get_event_ln_likelihood_ratio_svd_endtime_mass(coinc_bytes)

    # Using the zerolag log likelihood ratio value event,
    # and the foreground/background model information provided
    # in ranking_data.xml.gz, compute the ln(f/b) value for this event
    zerolag_ln_likelihood_ratios = np.array([event_ln_likelihood_ratio])
    log.info('Computing f_over_b from ranking_data.xml.gz')
    try:
        ln_f_over_b = _get_ln_f_over_b(ranking_data_bytes,
                                       zerolag_ln_likelihood_ratios)
    except ValueError:
        log.exception("NaN encountered, using approximate method ...")
        return p_astro_other.compute_p_astro(snr,
                                             far,
                                             event_mass1,
                                             event_mass2)

    # Compute astrophysical Bayes factor
    astro_bayesfac = np.exp(ln_f_over_b)[0]

    # Read mean values from url file
    mean_values_dict = p_astro_other.read_mean_values(url="p_astro_url")

    # Compute categorical p_astro values
    p_astro_values = \
        p_astro_other.evaluate_p_astro_from_bayesfac(astro_bayesfac,
                                                     mean_values_dict,
                                                     event_mass1,
                                                     event_mass2,
                                                     num_bins=4)

    # Dump values in json file
    return json.dumps(p_astro_values)
