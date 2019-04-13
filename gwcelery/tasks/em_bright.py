"""Qualitative source classification for CBC events."""
import json
import pickle
from urllib import error, request

from ligo import computeDiskMass, em_bright

from celery.utils.log import get_task_logger
from ..import app

log = get_task_logger(__name__)


def _em_bright(m1, m2, c1, c2, threshold=3.0):
    """This is the place-holder function for the source classfication pipeline.
    This placeholder code will only act upon the mass2 point estimate value and
    classify the systems as whether they have a neutron or not."""
    disk_mass = computeDiskMass.computeDiskMass(m1, m2, c1, c2)
    p_ns = 1.0 if m2 <= threshold else 0.0
    p_emb = 1.0 if disk_mass > 0.0 or m1 < threshold else 0.0
    return p_ns, p_emb


@app.task(shared=False)
def classifier_other(args, graceid):
    """
    Returns the boolean probability of having a NS component
    and the probability of having non-zero disk mass. This
    method is used for pipelines that do not provide the data
    products necessary for computation of the source properties
    probabilities.

    Parameters
    ----------
    args : tuple
        Tuple containing (m1, m2, spin1z, spin2z, snr)
    graceid : str
        The graceid of the event

    Returns
    -------
    str
        JSON formatted string storing ``HasNS`` and ``HasRemnant``
        probabilities

    Example
    -------
    >>> em_bright.classifier_other((2.0, 1.0, 0.0, 0.0, 10.), 'S123456')
    '{"HasNS": 1.0, "HasRemnant": 1.0}'
    """
    mass1, mass2, chi1, chi2, snr = args
    p_ns, p_em = _em_bright(mass1, mass2, chi1, chi2)

    data = json.dumps({
        'HasNS': p_ns,
        'HasRemnant': p_em
    })
    return data


@app.task(shared=False)
def classifier_gstlal(args, graceid):
    """
    Returns the probability of having a NS component and the probability
    of having non-zero disk mass in the detected event.
    This method will be using the data products obtained from the weekly
    supervised learning runs for injections campaigns.
    The data products are in pickle formatted RandomForestClassifier objects.
    The method predict_proba of these objects provides us the probabilities
    of the coalesence being EM-Bright and existence of neutron star in the
    binary.

    Parameters
    ----------
    args : tuple
        Tuple containing (m1, m2, spin1z, spin2z, snr)
    graceid : str
        The graceid of the event

    Returns
    -------
    str
        JSON formatted string storing ``HasNS`` and ``HasRemnant``
        probabilities

    Notes
    -----
    This task would only work from within the CIT cluster.
    """
    mass1, mass2, chi1, chi2, snr = args
    try:
        response = request.urlopen(app.conf['em_bright_url'])
        ns_classifier, emb_classifier, scaler, filename = \
            pickle.loads(response.read())
        kwargs = {'ns_classifier': ns_classifier,
                  'emb_classifier': emb_classifier,
                  'scaler': scaler}
    except (pickle.UnpicklingError, error.HTTPError):
        kwargs = {}
        log.exception("Error in unpickling classifier or 404. Using defaults.")

    p_ns, p_em = em_bright.source_classification(mass1, mass2,
                                                 chi1, chi2,
                                                 snr, **kwargs)

    data = json.dumps({
        'HasNS': p_ns,
        'HasRemnant': p_em
    })
    return data
