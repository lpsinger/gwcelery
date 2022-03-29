"""Computation of ``p_astro`` by source category and utilities
related to ``p_astro.json`` source classification files.
See Kapadia et al (2019), :doi:`10.1088/1361-6382/ab5f2d`, for details.
"""
import io
import json

from celery.utils.log import get_task_logger
from ligo import p_astro_computation as pastrocomp
from matplotlib import pyplot as plt
import numpy as np

from . import gracedb, igwn_alert
from .. import app
from ..util import closing_figures, PromiseProxy, read_json

MEAN_VALUES_DICT = PromiseProxy(
    read_json, ('ligo.data', 'H1L1V1-mean_counts-1126051217-61603201.json'))

THRESHOLDS_DICT = PromiseProxy(
    read_json, ('ligo.data', 'H1L1V1-pipeline-far_snr-thresholds.json'))

P_ASTRO_LIVETIME = PromiseProxy(
    read_json, ('ligo.data', 'p_astro_livetime.json'))


log = get_task_logger(__name__)


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
    snr_choice = pastrocomp.choose_snr(far,
                                       snr,
                                       pipeline,
                                       instruments,
                                       THRESHOLDS_DICT)

    # Define constants to compute bayesfactors
    snr_star = 8.5
    far_star = 1 / (30 * 86400)

    # Compute astrophysical bayesfactor for
    # GraceDB event
    fground = 3 * snr_star**3 / (snr_choice**4)
    bground = far / far_star
    astro_bayesfac = fground / bground

    # Update terrestrial count based on far threshold
    lam_0 = far_star * P_ASTRO_LIVETIME['p_astro_livetime']
    mean_values_dict = dict(MEAN_VALUES_DICT)
    mean_values_dict["counts_Terrestrial"] = lam_0

    # Compute categorical p_astro values
    p_astro_values = \
        pastrocomp.evaluate_p_astro_from_bayesfac(astro_bayesfac,
                                                  mean_values_dict,
                                                  mass1,
                                                  mass2)
    # Dump mean values in json file
    return json.dumps(p_astro_values)


def _format_prob(prob):
    if prob >= 1:
        return '100%'
    elif prob <= 0:
        return '0%'
    elif prob > 0.99:
        return '>99%'
    elif prob < 0.01:
        return '<1%'
    else:
        return '{}%'.format(int(np.round(100 * prob)))


@app.task(shared=False)
@closing_figures()
def plot(contents):
    """Make a visualization of the source classification.

    Parameters
    ----------
    contents : str, bytes
        The contents of the ``p_astro.json`` file.

    Returns
    -------
    png : bytes
        The contents of a PNG file.

    Notes
    -----
    The unusually small size of the plot (2.5 x 2 inches) is optimized for
    viewing in GraceDB's image display widget.

    Examples
    --------
    .. plot::
       :include-source:

       >>> from gwcelery.tasks import p_astro
       >>> contents = '''
       ... {"Terrestrial": 0.001, "BNS": 0.65, "NSBH": 0.20,
       ... "BBH": 0.059}
       ... '''
       >>> p_astro.plot(contents)

    """
    # Explicitly use a non-interactive Matplotlib backend.
    plt.switch_backend('agg')

    classification = json.loads(contents)
    outfile = io.BytesIO()

    probs, names = zip(
        *sorted(zip(classification.values(), classification.keys())))

    with plt.style.context('seaborn-white'):
        fig, ax = plt.subplots(figsize=(2.5, 2))
        ax.barh(names, probs)
        for i, prob in enumerate(probs):
            ax.annotate(_format_prob(prob), (0, i), (4, 0),
                        textcoords='offset points', ha='left', va='center')
        ax.set_xlim(0, 1)
        ax.set_xticks([])
        ax.tick_params(left=False)
        for side in ['top', 'bottom', 'right']:
            ax.spines[side].set_visible(False)
        fig.tight_layout()
        fig.savefig(outfile, format='png')
    return outfile.getvalue()


@igwn_alert.handler('superevent',
                    'mdc_superevent',
                    shared=False)
def handle(alert):
    """LVAlert handler to plot and upload a visualization of every
    ``p_astro.json`` that is added to a superevent.
    """
    graceid = alert['uid']
    filename = 'p_astro.json'

    if alert['alert_type'] == 'log' and alert['data']['filename'] == filename:
        (
            gracedb.download.s(filename, graceid)
            |
            plot.s()
            |
            gracedb.upload.s(
                filename.replace('.json', '.png'), graceid,
                message=(
                    'Source classification visualization from '
                    '<a href="/api/superevents/{graceid}/files/{filename}">'
                    '{filename}</a>').format(
                        graceid=graceid, filename=filename),
                tags=['em_follow', 'p_astro', 'public']
            )
        ).delay()
