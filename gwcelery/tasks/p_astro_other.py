"""Module containing the computation of p_astro by source category
   See https://dcc.ligo.org/LIGO-T1800072 for details.
"""
import json
from urllib import error, request

from celery.utils.log import get_task_logger
import numpy as np

from ..import app

log = get_task_logger(__name__)


def p_astro_update(category, event_bayesfac_dict, mean_values_dict):
    """
    Compute `p_astro` for a new event using mean values
    of Poisson expected counts constructed from all the
    previous events. Invoked with every new GraceDB entry.

    Parameters
    ----------
    category : string
        source category
    event_bayesfac_dict : dictionary
        event Bayes factors
    mean_values_dict : dictionary
        mean values of Poisson counts

    Returns
    -------
    p_astro : float
        p_astro by source category
    """
    if category == "counts_Terrestrial":
        numerator = mean_values_dict["counts_Terrestrial"]
    else:
        numerator = \
            event_bayesfac_dict[category] * mean_values_dict[category]

    denominator = mean_values_dict["counts_Terrestrial"] + \
        np.sum([mean_values_dict[key] * event_bayesfac_dict[key]
                for key in event_bayesfac_dict.keys()])

    return numerator / denominator


def evaluate_p_astro_from_bayesfac(astro_bayesfac,
                                   mean_values_dict,
                                   mass1,
                                   mass2,
                                   bin_num=None,
                                   url_weights=None):
    """
    Evaluates `p_astro` for a new event using Bayes factor,
    masses, and number of astrophysical categories.
    Invoked with every new GraceDB entry.

    Parameters
    ----------
    astro_bayesfac : float
        astrophysical Bayes factor
    mean_values_dict: dictionary
        mean values of Poisson counts
    mass1 : float
        event mass1
    mass2 : float
        event mass2
    bin_num : int
        bin number for the event
    url_weights: str
        url pointing to weights file

    Returns
    -------
    p_astro : dictionary
        p_astro for all source categories
    """

    if bin_num is not None and url_weights is not None:
        a_hat_bns, a_hat_bbh, a_hat_nsbh, a_hat_mg, num_bins = \
            make_weights_from_histograms(url_weights, bin_num, mass1, mass2)
    else:
        a_hat_bns, a_hat_bbh, a_hat_nsbh, a_hat_mg, num_bins = \
            make_weights_from_hardcuts(mass1, mass2)

    # Compute category-wise Bayes factors
    # from astrophysical Bayes factor
    rescaled_fb = num_bins * astro_bayesfac
    bns_bayesfac = a_hat_bns * rescaled_fb
    nsbh_bayesfac = a_hat_nsbh * rescaled_fb
    bbh_bayesfac = a_hat_bbh * rescaled_fb
    mg_bayesfac = a_hat_mg * rescaled_fb

    # Construct category-wise Bayes factor dictionary
    event_bayesfac_dict = {"counts_BNS": bns_bayesfac,
                           "counts_NSBH": nsbh_bayesfac,
                           "counts_BBH": bbh_bayesfac,
                           "counts_MassGap": mg_bayesfac}

    # Compute the p-astro values for each source category
    # using the mean values
    p_astro_values = {}
    for category in mean_values_dict:
        p_astro_values[category.split("_")[1]] = \
            p_astro_update(category=category,
                           event_bayesfac_dict=event_bayesfac_dict,
                           mean_values_dict=mean_values_dict)

    return p_astro_values


def read_mean_values(url):
    """
    Reads the mean values in the file pointed to by
    a url.

    Parameters
    ----------
    url : string
        url pointing at location of counts mean file

    Returns
    -------
    mean_values_dict : dictionary
        mean values read from url file
    """

    try:
        response = request.urlopen(app.conf[url])
        mean_values_dict = json.loads(response.read())
        response.close()
    except (ValueError, error.URLError):
        # Fix mean values (1 per source category) from O1-O2
        mean_values_dict = {"counts_BNS": 2.11050326523,
                            "counts_NSBH": 1.56679410666,
                            "counts_BBH": 9.26042350393,
                            "counts_MassGap": 2.40800240248,
                            "counts_Terrestrial": 3923}
    return mean_values_dict


def make_weights_from_hardcuts(mass1, mass2):
    """
    Construct binary weights from component masses
    based on cuts in component mass space that
    define astrophyscal source categories.
    To be used for MBTA, PyCBC and SPIIR.

    Parameters
    ----------
    mass1 : float
        heavier component mass of the event
    mass2 : float
        lighter component mass of the event

    Returns
    -------
    a_bns, a_bbh, a_nshb, a_mg : floats
        binary weights (i.e, 1 or 0)
    """

    a_hat_bns = int(mass1 <= 3 and mass2 <= 3)
    a_hat_bbh = int(mass1 > 5 and mass2 > 5)
    a_hat_nsbh = int(min(mass1, mass2) <= 3 and
                     max(mass1, mass2) > 5)
    a_hat_mg = int(3 < mass1 <= 5 or 3 < mass2 <= 5)
    num_bins = 4

    return a_hat_bns, a_hat_bbh, a_hat_nsbh, a_hat_mg, num_bins


def make_weights_from_histograms(url_weights, bin_num, mass1, mass2):
    """
    Construct binary weights from bin number
    provided by GstLAL, and a weights matrix
    pre-constructed and stored in a file, to
    be read from a url. If that doesn't work,
    construct binary weights.

    Parameters
    ----------
    url_weights : string
        url pointing at location of weights file
    bin_num : int
        bin number for event
    mass1 : float
        heavier component mass of the event
    mass2 : float
        lighter component mass of the event

    Returns
    -------
    a_bns, a_bbh, a_nshb, a_mg : floats
        binary weights (i.e, 1 or 0)
    """

    try:
        response = request.urlopen(app.conf[url_weights])
        activation_counts = json.loads(response.read())
        response.close()

    except(ValueError, error.URLError):
        activation_counts = None

    if activation_counts is not None:
        a_bns = np.array(activation_counts['bns'], dtype=float)
        a_hat_bns = a_bns[bin_num] / np.sum(a_bns)
        a_bbh = np.array(activation_counts['bbh'], dtype=float)
        a_hat_bbh = a_bbh[bin_num] / np.sum(a_bbh)
        a_nsbh = np.array(activation_counts['nsbh'], dtype=float)
        a_hat_nsbh = a_nsbh[bin_num] / np.sum(a_nsbh)
        a_mg = np.array(activation_counts['mg'], dtype=float)
        a_hat_mg = a_mg[bin_num] / np.sum(a_mg)
        num_bins = len(a_bns)
    else:
        a_hat_bns, a_hat_bbh, a_hat_nsbh, a_hat_mg, num_bins = \
            make_weights_from_hardcuts(mass1, mass2)

    return a_hat_bns, a_hat_bbh, a_hat_nsbh, a_hat_mg, num_bins


@app.task(shared=False)
def compute_p_astro(snr, far, mass1, mass2):
    """
    Task to compute `p_astro` by source category.

    Parameters
    ----------
    snr : float
        event's snr
    far : float
        event's cfar
    mass1 : float
        event's mass1
    mass2 : float
        event's mass2

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

    url = "p_astro_url"

    # Read mean values from file
    mean_values_dict = read_mean_values(url=url)

    # Define constants to compute bayesfactors
    snr_star = 8.5
    far_star = 1 / (30 * 86400)

    # Compute astrophysical bayesfactor for
    # GraceDB event
    fground = 3 * snr_star**3 / (snr**4)
    bground = far / far_star
    astro_bayesfac = fground / bground

    # Compute categorical p_astro values
    p_astro_values = evaluate_p_astro_from_bayesfac(astro_bayesfac,
                                                    mean_values_dict,
                                                    mass1,
                                                    mass2)
    # Dump mean values in json file
    return json.dumps(p_astro_values)
