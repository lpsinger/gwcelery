"""Utilities related to ``p_astro.json`` source classification files."""
import io
import json

from matplotlib import pyplot as plt
import numpy as np

from . import gracedb, lvalert
from .. import app


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
       ... "MassGap": 0.10, "BBH": 0.059}
       ... '''
       >>> p_astro.plot(contents)
    """
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


@lvalert.handler('superevent',
                 'mdc_superevent',
                 shared=False)
def handle(alert):
    """LVAlert handler to plot and upload a visualization of every
    ``p_astro.json`` that is added to a superevent."""
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
