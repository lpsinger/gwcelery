"""Qualitative source classification for CBC events."""
import json

from ligo import computeDiskMass, em_bright

from celery.utils.log import get_task_logger
from ..import app
from ..util.tempfile import NamedTemporaryFile

log = get_task_logger(__name__)


@app.task(shared=False)
def em_bright_posterior_samples(posterior_file_content):
    """Returns the probability of having a NS component and remnant
    using LALInference posterior samples.

    Parameters
    ----------
    posterior_file_content : hdf5 posterior file content

    Returns
    -------
    str
        JSON formatted string storing ``HasNS`` and ``HasRemnant``
        probabilities

    Example
    ---------
    >>> em_bright_posterior_samples(GraceDb().files('S190930s',
    ... 'LALInference.posterior_samples.hdf5').read())
    {"HasNS": 0.014904901243599122, "HasRemnant": 0.0}

    """
    with NamedTemporaryFile(content=posterior_file_content) as samplefile:
        filename = samplefile.name
        has_ns, has_remnant = em_bright.source_classification_pe(filename)
    data = json.dumps({
        'HasNS': has_ns,
        'HasRemnant': has_remnant
    })
    return data


def _em_bright(m1, m2, c1, c2, threshold=3.0):
    """This is the place-holder function for the source classfication pipeline.
    This placeholder code will only act upon the mass2 point estimate value and
    classify the systems as whether they have a neutron or not.
    """
    disk_mass = computeDiskMass.computeDiskMass(m1, m2, c1, c2)
    p_ns = 1.0 if m2 <= threshold else 0.0
    p_emb = 1.0 if disk_mass > 0.0 or m1 < threshold else 0.0
    return p_ns, p_emb


@app.task(shared=False)
def classifier_other(args, graceid):
    """Returns the boolean probability of having a NS component and the
    probability of having non-zero disk mass. This method is used for pipelines
    that do not provide the data products necessary for computation of the
    source properties probabilities.

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
    """Returns the probability of having a NS component and the probability of
    having non-zero disk mass in the detected event. This method will be using
    the data products obtained from the weekly supervised learning runs for
    injections campaigns. The data products are in pickle formatted
    RandomForestClassifier objects. The method predict_proba of these objects
    provides us the probabilities of the coalesence being EM-Bright and
    existence of neutron star in the binary.

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
    p_ns, p_em = em_bright.source_classification(*args)

    data = json.dumps({
        'HasNS': p_ns,
        'HasRemnant': p_em
    })
    return data
