"""Computation of `p_astro` by source category.
   See Kapadia et al (2019), arXiv:1903.06881, for details.
"""
import json
from urllib import error, request

from celery.utils.log import get_task_logger
from ligo import p_astro_computation as pastrocomp

from ..import app

log = get_task_logger(__name__)


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

    # Read mean values from file
    mean_values_dict = read_mean_values()
    url_key = "p_astro_thresh_url"

    # Read thresholds on FAR and SNR from file
    response = request.urlopen(app.conf[url_key])
    thresholds_dict = json.load(response)
    response.close()

    # Ensure SNR does not increase indefinitely beyond limiting FAR
    # for MBTA and PyCBC events
    snr_choice = pastrocomp.choose_snr(far,
                                       snr,
                                       pipeline,
                                       instruments,
                                       thresholds_dict)

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
    p_astro_values = \
        pastrocomp.evaluate_p_astro_from_bayesfac(astro_bayesfac,
                                                  mean_values_dict,
                                                  mass1,
                                                  mass2)
    # Dump mean values in json file
    return json.dumps(p_astro_values)
