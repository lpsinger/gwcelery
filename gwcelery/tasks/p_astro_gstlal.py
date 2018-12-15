"""Module containing the computation of p_astro by source category
   See https://dcc.ligo.org/LIGO-T1800072 for details.
"""
import io
import json

from celery.utils.log import get_task_logger
from glue.ligolw import ligolw
from glue.ligolw.ligolw import LIGOLWContentHandler
from glue.ligolw import array as ligolw_array
from glue.ligolw import param as ligolw_param
from glue.ligolw import utils as ligolw_utils
from glue.ligolw import lsctables
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


def _get_ln_f_over_b(ranking_data_bytes, ln_likelihood_ratios):
    ranking_data_xmldoc, _ = ligolw_utils.load_fileobj(
        io.BytesIO(ranking_data_bytes), contenthandler=_ContentHandler)
    rankingstatpdf = _parse_likelihood_control_doc(ranking_data_xmldoc)
    # affect the zeroing of the PDFs below threshold by hacking the
    # histograms. Do the indexing ourselves to not 0 the bin @ threshold
    ln_likelihood_ratio_threshold = \
        app.conf['p_astro_gstlal_ln_likelihood_threshold']
    noise_lr_lnpdf = rankingstatpdf.noise_lr_lnpdf
    rankingstatpdf.noise_lr_lnpdf.array[
        :noise_lr_lnpdf.bins[0][ln_likelihood_ratio_threshold]] \
        = 0.
    rankingstatpdf.noise_lr_lnpdf.normalize()
    signal_lr_lnpdf = rankingstatpdf.signal_lr_lnpdf
    rankingstatpdf.signal_lr_lnpdf.array[
        :signal_lr_lnpdf.bins[0][ln_likelihood_ratio_threshold]] \
        = 0.
    rankingstatpdf.signal_lr_lnpdf.normalize()
    zero_lag_lr_lnpdf = rankingstatpdf.zero_lag_lr_lnpdf
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
    coinc_xmldoc, _ = ligolw_utils.load_fileobj(
        io.BytesIO(coinc_bytes), contenthandler=_ContentHandler)
    coinc_event, = lsctables.CoincTable.get_table(coinc_xmldoc)
    coinc_inspiral, = lsctables.CoincInspiralTable.get_table(coinc_xmldoc)
    sngl_inspiral = lsctables.SnglInspiralTable.get_table(coinc_xmldoc)

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


# This is the function that computes p-astro for a new
# event using mean values of Poisson expected counts
# constructed from all the previous events. This is
# the function that will be invoked with every new
# GraceDB entry


def p_astro_update(category, event_bayesfac_dict, mean_values_dict):

    if category == "Terr":
        numerator = mean_values_dict["Terr"]
    else:
        numerator = \
            event_bayesfac_dict[category]*mean_values_dict[category]

    denominator = mean_values_dict["Terr"] + \
        np.sum([mean_values_dict[key]*event_bayesfac_dict[key]
                for key in event_bayesfac_dict.keys()])

    return numerator/denominator


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
    {'BNS': 0.999, 'BBH': 0.0, 'NSBH': 0.0, 'Terr': 0.001}
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
    # resort to approximate computation if NaN encountered
    try:
        ln_f_over_b = _get_ln_f_over_b(ranking_data_bytes,
                                       zerolag_ln_likelihood_ratios)
    except ValueError:
        log.warning("NaN encountered, using approximate method...")
        return p_astro_other.compute_p_astro(snr,
                                             far,
                                             event_mass1,
                                             event_mass2)
    else:
        num_bins = 3
        mean_bns = 2.07613829518
        mean_nsbh = 1.65747751787
        mean_bbh = 11.8941873831
        mean_terr = 3923

        a_hat_bns = int(event_mass1 <= 3 and event_mass2 <= 3)
        a_hat_bbh = int(event_mass2 > 3 and event_mass2 > 3)
        a_hat_nsbh = int(min([event_mass1, event_mass2]) <= 3 and
                         max([event_mass1, event_mass2]) > 3)

        # Fix mean values (1 per source category) from
        mean_values_dict = {"BNS": mean_bns,
                            "NSBH": mean_nsbh,
                            "BBH": mean_bbh,
                            "Terr": mean_terr}

        # These are the bayes factor values that need to be
        # constructed with every new event/GraceDB upload
        rescaled_fb = num_bins*np.exp(ln_f_over_b)[0]
        bns_bayesfac = a_hat_bns*rescaled_fb
        nsbh_bayesfac = a_hat_nsbh*rescaled_fb
        bbh_bayesfac = a_hat_bbh*rescaled_fb
        event_bayesfac_dict = {"BNS": bns_bayesfac,
                               "NSBH": nsbh_bayesfac,
                               "BBH": bbh_bayesfac}

        # Compute the p-astro values for each source category
        # using the mean values
        p_astro_values = {}
        for category in mean_values_dict:
            p_astro_values[category] = \
                p_astro_update(category=category,
                               event_bayesfac_dict=event_bayesfac_dict,
                               mean_values_dict=mean_values_dict)
        return json.dumps(p_astro_values)
