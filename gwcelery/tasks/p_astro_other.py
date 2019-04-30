"""Computation of `p_astro` by source category.
   See Kapadia et al (2019), arXiv:1903.06881, for details.
"""
import json
from os.path import basename
from urllib import error, request

from celery.utils.log import get_task_logger
import numpy as np

from ..import app

log = get_task_logger(__name__)


def p_astro_update(category, event_bayesfac_dict, mean_values_dict):
    """
    Compute `p_astro` for a new event using mean values of Poisson expected
    counts constructed from all the previous events. Invoked with every new
    GraceDB entry.

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
                                   spin1z=None,
                                   spin2z=None,
                                   url_weights_key=None):
    """
    Evaluates `p_astro` for a new event using Bayes factor, masses, and number
    of astrophysical categories. Invoked with every new GraceDB entry.

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
    spin1z : float
        event spin1z
    spin2z : float
        event spin2z
    url_weights_key: str
        url config key pointing to weights file

    Returns
    -------
    p_astro : dictionary
        p_astro for all source categories
    """

    if url_weights_key is None:
        a_hat_bns, a_hat_bbh, a_hat_nsbh, a_hat_mg, num_bins = \
            make_weights_from_hardcuts(mass1, mass2)
    else:
        a_hat_bns, a_hat_bbh, a_hat_nsbh, a_hat_mg, num_bins = \
            make_weights_from_histograms(url_weights_key,
                                         mass1,
                                         mass2,
                                         spin1z,
                                         spin2z)

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


def read_mean_values():
    """
    Reads the mean values in the file pointed to by a url.

    Returns
    -------
    mean_values_dict : dictionary
        mean values read from url file
    """

    try:
        url_key = "p_astro_url"
        response = request.urlopen(app.conf[url_key])
        mean_values_dict = json.load(response)
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
    Construct binary weights from component masses based on cuts in component
    mass space that define astrophysical source categories. To be used for
    MBTA, PyCBC and SPIIR.

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


def closest_template(params, params_list):
    """
    Associate event's template to a template in the template bank. The assumed
    bank is the one used by Gstlal. Hence, for Gstlal events, the association
    should be exact, up to rounding errors.

    Parameters
    ----------
    params : tuple of floats
        intrinsic params of event template
    params_list: list of strings
        list of template bank's template params

    Returns
    -------
    key : string
        params of template in template bank
        matching event's template
    """
    params_array = np.array(list(map(eval, params_list)))
    idx = np.argmin(np.sum((params_array-params)**2, axis=1))
    num_params = len(params_array[idx])
    template = params_array[idx]
    string = '(' + ', '.join(['{:3.8f}']*num_params) + ')'
    key = string.format(*template)
    return key


def make_weights_from_histograms(url_weights_key,
                                 mass1,
                                 mass2,
                                 spin1z,
                                 spin2z):
    """
    Construct binary weights from bin number provided by GstLAL, and a weights
    matrix pre-constructed and stored in a file, to be read from a url. The
    weights are keyed on template parameters of Gstlal's template bank. If that
    doesn't work, construct binary weights.

    Parameters
    ----------
    url_weights_key : string
        url config key pointing at
        location of weights file
    mass1 : float
        heavier component mass of the event
    mass2 : float
        lighter component mass of the event
    spin1z : float
        z component spin of heavier mass
    spin2z : float
        z component spin of lighter mass

    Returns
    -------
    a_bns, a_bbh, a_nsbh, a_mg : floats
        mass-based template weights
    """

    try:
        response = request.urlopen(app.conf[url_weights_key])
        activation_counts = json.load(response)
        response.close()

    except(ValueError, error.URLError):
        activation_counts = None

    if activation_counts is None:
        a_hat_bns, a_hat_bbh, a_hat_nsbh, a_hat_mg, num_bins = \
            make_weights_from_hardcuts(mass1, mass2)
    else:
        params = (mass1, mass2, spin1z, spin2z)
        params_list = list(activation_counts.keys())
        key = closest_template(params, params_list)
        event_weights_dict = activation_counts[key]
        source_types = np.sort(list(event_weights_dict.keys()))
        a_hat_bbh, a_hat_bns, a_hat_mg, a_hat_nsbh = \
            tuple([event_weights_dict[s] for s in source_types])
        filename = basename(app.conf[url_weights_key])
        num_bins = int(filename.split("-")[2].split("_")[1])

    return a_hat_bns, a_hat_bbh, a_hat_nsbh, a_hat_mg, num_bins


def choose_snr(far, snr, pipeline, instruments):
    """
    Given a pipeline and combination of instruments, return an SNR that does
    not exceed the SNR threshold for FARs below a FAR threshold. The SNR and
    FAR thresholds are read from a file containing these values keyed on
    pipelines and instrument combinations.

    Parameters
    ----------
    far : float
        false alarm rate of the event
    snr : float
        SNR of the event
    pipeline : string
        pipeline that posted the event
    instruments : set
        set of instruments that detected the event

    Returns
    -------
    snr : float
        limiting SNR value
    """

    if pipeline == "gstlal":
        snr_choice = snr
    else:
        response = request.urlopen(app.conf["p_astro_thresh_url"])
        threshold_dict = json.load(response)
        response.close()

        inst_sorted = ",".join(sorted(instruments))
        far_t = threshold_dict[pipeline][inst_sorted]["far"]
        snr_t = threshold_dict[pipeline][inst_sorted]["snr"]
        if far < far_t and snr > snr_t:
            snr_choice = snr_t
        else:
            snr_choice = snr

    return snr_choice


@app.task(shared=False)
def compute_p_astro(snr, far, mass1, mass2, pipeline, instruments):
    """
    Task to compute `p_astro` by source category.

    Parameters
    ----------
    snr : float
        event's SNR
    far : float
        event's cfar
    mass1 : float
        event's mass1
    mass2 : float
        event's mass2
    instruments : set
        set of instruments that detected the event

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

    # Ensure SNR does not increase indefinitely beyond limiting FAR
    # for MBTA and PyCBC events
    snr_choice = choose_snr(far, snr, pipeline, instruments)

    # Read mean values from file
    mean_values_dict = read_mean_values()

    # Define constants to compute bayesfactors
    snr_star = 8.5
    far_star = 1 / (30 * 86400)

    # Compute astrophysical bayesfactor for
    # GraceDB event
    fground = 3 * snr_star**3 / (snr_choice**4)
    bground = far / far_star
    astro_bayesfac = fground / bground

    # Update terrestrial count based on far threshold
    lam_0 = far_star * app.conf["p_astro_livetime"]
    mean_values_dict["counts_Terrestrial"] = lam_0

    # Compute categorical p_astro values
    p_astro_values = evaluate_p_astro_from_bayesfac(astro_bayesfac,
                                                    mean_values_dict,
                                                    mass1,
                                                    mass2)
    # Dump mean values in json file
    return json.dumps(p_astro_values)
