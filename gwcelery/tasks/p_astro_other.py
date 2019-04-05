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
                                   num_bins):
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
    num_bins: int
        number of astrophysical categories

    Returns
    -------
    p_astro : dictionary
        p_astro for all source categories
    """

    # Construct mass-based template-weights
    a_hat_bns = int(mass1 <= 3 and mass2 <= 3)
    a_hat_bbh = int(mass1 > 5 and mass2 > 5.)
    a_hat_nsbh = int(min(mass1, mass2) <= 3 and
                     max(mass1, mass2) > 5)
    a_hat_mg = int(3 < mass1 <= 5 or 3 < mass2 <= 5)

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

    # Read mean values from file
    mean_values_dict = read_mean_values(url="p_astro_url")

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
                                                    mass2,
                                                    num_bins=4)
    # Dump mean values in json file
    return json.dumps(p_astro_values)
