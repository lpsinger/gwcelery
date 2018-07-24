"""Module containing the computation of p_astro by source category
   See https://dcc.ligo.org/LIGO-T1800072 for details.
"""
import json

from celery.utils.log import get_task_logger
import numpy as np

from ..import app

log = get_task_logger(__name__)


def p_astro_update(category, event_bayesfac_dict, mean_values_dict):
    """
    This is the function that computes `p_astro` for a new
    event using mean values of Poisson expected counts
    constructed from all the previous events. This is
    the function that will be invoked with every new
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
    {'BNS': 0.999, 'BBH': 0.0, 'NSBH': 0.0, 'Terr': 0.001}
    """
    mean_bns = 2.07613829518
    mean_nsbh = 1.65747751787
    mean_bbh = 11.8941873831
    mean_terr = 3923
    snr_star = 8.5
    far_star = 1/(30*86400)
    num_bins = 3

    # Fix mean values (1 per source category) from
    mean_values_dict = {"BNS": mean_bns,
                        "NSBH": mean_nsbh,
                        "BBH": mean_bbh,
                        "Terr": mean_terr}

    # These are the bayes factor values that need to be
    # constructed with every new event/GraceDB upload
    fground = 3*snr_star/(snr**4)
    bground = far/far_star

    a_hat_bns = int(mass1 <= 3 and mass2 <= 3)
    a_hat_bbh = int(mass2 > 3 and mass2 > 3)
    a_hat_nsbh = int(min([mass1, mass2]) <= 3 and max([mass1, mass2]) > 3)

    rescaled_fb = num_bins*fground/bground
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
