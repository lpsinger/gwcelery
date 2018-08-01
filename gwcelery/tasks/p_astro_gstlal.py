"""Module containing the computation of p_astro by source category
   See https://dcc.ligo.org/LIGO-T1800072 for details.
"""
import io
import json
import os
import sqlite3

from celery.utils.log import get_task_logger
from celery.exceptions import Ignore
from glue.ligolw import ligolw
from glue.ligolw.ligolw import LIGOLWContentHandler
from glue.ligolw import array as ligolw_array
from glue.ligolw import param as ligolw_param
from glue.ligolw import dbtables
from glue.ligolw import utils as ligolw_utils
from glue.ligolw import lsctables
from lalinspiral import thinca
from lal import rate
from ligo.p_astro import SourceType, MarginalizedPosterior
import numpy as np
import pkg_resources

from ..import app
from ..util import PromiseProxy

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
            int(sngl_inspiral[0].Gamma1),
            coinc_inspiral.end_time,
            coinc_inspiral.mass)


def _load_search_database():
    filename = app.conf['p_astro_gstlal_trigger_db']
    # FIXME the gstlal trigger database path is specific to the CIT
    # cluster. Gentle exit against opening a non-existant database outside CIT
    if not os.path.exists(filename):
        raise Ignore(
            "Gstlal trigger database {} not found".format(filename))
    return sqlite3.connect('file:{}?mode=ro'.format(filename), uri=True)


# Lazily load search database
connection = PromiseProxy(_load_search_database)


def _load_search_results(end_time, mass, ln_likelihood_ratio_threshold):
    """Queries SQLite file for background trigger data.
    The query has an extra check to make sure the event is not
    double counted.
    """
    cur = connection.cursor()

    xmldoc = dbtables.get_xml(connection)
    definer_id = lsctables.CoincDefTable.get_table(xmldoc).get_coinc_def_id(
        thinca.InspiralCoincDef.search,
        thinca.InspiralCoincDef.search_coinc_type,
        create_new=False)
    cur.execute("""
SELECT
        coinc_event.likelihood,
        (
        SELECT sngl_inspiral.Gamma1
        FROM
                sngl_inspiral JOIN coinc_event_map ON (
                        coinc_event_map.table_name == "sngl_inspiral"
                        AND coinc_event_map.event_id == sngl_inspiral.event_id
                )
        WHERE
        coinc_event_map.coinc_event_id == coinc_inspiral.coinc_event_id
        LIMIT 1
        ),
        EXISTS (
    SELECT
*
    FROM
time_slide
    WHERE
time_slide.time_slide_id == coinc_event.time_slide_id
AND time_slide.offset != 0
        )
FROM
        coinc_event JOIN coinc_inspiral ON (
    coinc_inspiral.coinc_event_id == coinc_event.coinc_event_id
        )
WHERE
        coinc_event.coinc_def_id == ?
        AND coinc_event.likelihood >= ?
        AND coinc_inspiral.end_time != ?
        AND coinc_inspiral.mass != ?""", (definer_id,
                                          ln_likelihood_ratio_threshold,
                                          end_time,
                                          mass))
    ln_likelihood_ratio, svd_banks, is_background = np.array(cur.fetchall()).T
    background_ln_likelihood_ratios = \
        ln_likelihood_ratio[is_background.astype(bool)]
    zerolag_ln_likelihood_ratios = \
        ln_likelihood_ratio[np.logical_not(is_background.astype(bool))]
    svd_banks = svd_banks.astype(int)

    return background_ln_likelihood_ratios, \
        zerolag_ln_likelihood_ratios, svd_banks


def _load_counts(name):
    # FIXME txt files will need to be queried from sqlite dbs
    filename = pkg_resources.resource_filename(
        __name__, '../data/p_astro_gstlal/{}_wellfound_hits.txt'.format(name))

    # Construction of the weights
    a = np.recfromtxt(filename, names=True)['hit_count']
    a_hat = a / a.sum()
    return a_hat


# Lazily load weights
a_hat_bns = PromiseProxy(_load_counts, ('bns',))
a_hat_nsbh = PromiseProxy(_load_counts, ('nsbh',))
a_hat_bbh = PromiseProxy(_load_counts, ('bbh',))


def _get_counts_instance(ln_f_over_b,
                         svd_bank_nums,
                         prior_type="Uniform"):
    num_svd_bins = len(a_hat_bns)

    w_bns = num_svd_bins*np.take(a_hat_bns, svd_bank_nums)
    w_nsbh = num_svd_bins*np.take(a_hat_nsbh, svd_bank_nums)
    w_bbh = num_svd_bins*np.take(a_hat_bbh, svd_bank_nums)

    num_f_over_b = len(ln_f_over_b)
    w_terr = np.ones(num_f_over_b)

    fb = np.exp(ln_f_over_b)

    return MarginalizedPosterior(f_divby_b=fb, prior_type=prior_type,
                                 terr_source=SourceType(label="Terr",
                                                        w_fgmc=w_terr),
                                 fix_sources={"Terr": num_f_over_b},
                                 bns_inst=SourceType(label="BNS",
                                                     w_fgmc=w_bns),
                                 bbh_inst=SourceType(label="BBH",
                                                     w_fgmc=w_bbh),
                                 nsbh_inst=SourceType(label="NSBH",
                                                      w_fgmc=w_nsbh),
                                 verbose=False)


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

    log.info(
        'Fetching ln_likelihood_ratio, svd bin, endtime, mass from coinc.xml')
    event_ln_likelihood_ratio, event_svd, event_endtime, event_mass = \
        _get_event_ln_likelihood_ratio_svd_endtime_mass(coinc_bytes)

    ln_likelihood_ratio_threshold = \
        app.conf['p_astro_gstlal_ln_likelihood_threshold']

    log.info('Querying trigger db to fetch zerolag ln_likelihood_ratios')

    background_ln_likelihood_ratios, zerolag_ln_likelihood_ratios, \
        svd_banks = _load_search_results(event_endtime,
                                         event_mass,
                                         ln_likelihood_ratio_threshold)

    svd_banks = np.append(svd_banks, event_svd)
    zerolag_ln_likelihood_ratios = np.append(
        zerolag_ln_likelihood_ratios, event_ln_likelihood_ratio)

    log.info('Computing f_over_b from ranking_data.xml.gz')
    ln_f_over_b = _get_ln_f_over_b(ranking_data_bytes,
                                   zerolag_ln_likelihood_ratios)

    log.info('Creating FGMC MarginalizedPosterior')
    event_counts_instance = \
        _get_counts_instance(ln_f_over_b,
                             svd_banks,
                             prior_type=app.conf['p_astro_gstlal_prior_type'])

    num_f_over_b = len(ln_f_over_b)

    categories = ['BNS', 'BBH', 'NSBH', 'Terr']
    p_astro_values = {}
    for category in categories:
        p_astro_values[category] = \
            event_counts_instance.pastro(categories=[category],
                                         trigger_idx=num_f_over_b-1)[0]
    return json.dumps(p_astro_values)
