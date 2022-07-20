"""Annotations for sky maps."""
import io
import os
import tempfile

from astropy.io import fits
from astropy import table
from celery import group
from celery.exceptions import Ignore
from ligo.skymap.tool import ligo_skymap_flatten
from ligo.skymap.tool import ligo_skymap_from_samples
from ligo.skymap.tool import ligo_skymap_plot
from ligo.skymap.tool import ligo_skymap_plot_volume
from matplotlib import pyplot as plt
import numpy as np

from . import gracedb
from . import igwn_alert
from ..import app
from ..jinja import env
from ..util.cmdline import handling_system_exit
from ..util.matplotlib import closing_figures
from ..util.tempfile import NamedTemporaryFile


@app.task(ignore_result=True, shared=False)
def annotate_fits(filecontents, versioned_filename, graceid, tags):
    """Perform annotations on a sky map.

    This function downloads a FITS file and then generates and uploads all
    derived images as well as an HTML dump of the FITS header.
    """
    multiorder_extension = '.multiorder.fits'
    flat_extension = '.fits'

    if multiorder_extension in versioned_filename:
        extension = multiorder_extension
        multiorder = True
    else:
        extension = flat_extension
        multiorder = False

    filebase, _, _ = versioned_filename.partition(extension)

    header_msg = (
        'FITS headers for <a href="/api/superevents/{graceid}/files/'
        '{versioned_filename}">{versioned_filename}</a>').format(
            graceid=graceid, versioned_filename=versioned_filename)
    allsky_msg = (
        'Mollweide projection of <a href="/api/superevents/{graceid}/files/'
        '{versioned_filename}">{versioned_filename}</a>').format(
            graceid=graceid, versioned_filename=versioned_filename)
    volume_msg = (
        'Volume rendering of <a href="/api/superevents/{graceid}/files/'
        '{versioned_filename}">{versioned_filename}</a>').format(
            graceid=graceid, versioned_filename=versioned_filename)
    flatten_msg = (
        'Flat-resolution fits file created from '
        '<a href="/api/superevents/{graceid}/files/'
        '{versioned_filename}">{versioned_filename}</a>').format(
            graceid=graceid, versioned_filename=versioned_filename)

    group(
        fits_header.s(versioned_filename)
        |
        gracedb.upload.s(
            filebase + '.html', graceid, header_msg, tags),

        plot_allsky.s()
        |
        gracedb.upload.s(
            filebase + '.png', graceid, allsky_msg, tags),

        annotate_fits_volume.s(
            filebase + '.volume.png', graceid, volume_msg, tags),

        *(
            [
                flatten.s(f'{filebase}.fits.gz')
                |
                gracedb.upload.s(
                    f'{filebase}.fits.gz', graceid, flatten_msg, tags)
            ] if multiorder else []
        )
    ).delay(filecontents)


def is_3d_fits_file(filecontents):
    """Determine if a FITS file has distance information."""
    with NamedTemporaryFile(content=filecontents) as fitsfile:
        return 'DISTNORM' in table.Table.read(fitsfile.name).colnames


@app.task(ignore_result=True, shared=False)
def annotate_fits_volume(filecontents, *args):
    """Perform annotations that are specific to 3D sky maps."""
    if is_3d_fits_file(filecontents):
        (
            plot_volume.s(filecontents)
            |
            gracedb.upload.s(*args)
        ).apply_async()


@app.task(shared=False)
def fits_header(filecontents, filename):
    """Dump FITS header to HTML."""
    template = env.get_template('fits_header.jinja2')
    with NamedTemporaryFile(content=filecontents) as fitsfile, \
            fits.open(fitsfile.name) as hdus:
        return template.render(filename=filename, hdus=hdus)


@app.task(shared=False)
@closing_figures()
def plot_allsky(filecontents, ra=None, dec=None):
    """Plot a Mollweide projection of a sky map using the command-line tool
    :doc:`ligo-skymap-plot <ligo.skymap:tool/ligo_skymap_plot>`.
    """
    # Explicitly use a non-interactive Matplotlib backend.
    plt.switch_backend('agg')

    with NamedTemporaryFile(mode='rb', suffix='.png') as pngfile, \
            NamedTemporaryFile(content=filecontents) as fitsfile, \
            handling_system_exit():
        if ra is not None and dec is not None:
            ligo_skymap_plot.main([fitsfile.name, '-o', pngfile.name,
                                   '--annotate', '--radec', str(ra), str(dec)])
        else:
            ligo_skymap_plot.main([fitsfile.name, '-o', pngfile.name,
                                   '--annotate', '--contour', '50', '90'])
        return pngfile.read()


@app.task(priority=1, queue='openmp', shared=False)
@closing_figures()
def plot_volume(filecontents):
    """Plot a 3D volume rendering of a sky map using the command-line tool
    :doc:`ligo-skymap-plot-volume <ligo.skymap:tool/ligo_skymap_plot_volume>`.
    """
    # Explicitly use a non-interactive Matplotlib backend.
    plt.switch_backend('agg')

    with NamedTemporaryFile(mode='rb', suffix='.png') as pngfile, \
            NamedTemporaryFile(content=filecontents) as fitsfile, \
            handling_system_exit():
        ligo_skymap_plot_volume.main([fitsfile.name, '-o',
                                      pngfile.name, '--annotate'])
        return pngfile.read()


@app.task(shared=False)
def flatten(filecontents, filename):
    """Convert a HEALPix FITS file from multi-resolution UNIQ indexing to the
    more common IMPLICIT indexing using the command-line tool
    :doc:`ligo-skymap-flatten <ligo.skymap:tool/ligo_skymap_flatten>`.
    """
    with NamedTemporaryFile(content=filecontents) as infile, \
            tempfile.TemporaryDirectory() as tmpdir, \
            handling_system_exit():
        outfilename = os.path.join(tmpdir, filename)
        ligo_skymap_flatten.main([infile.name, outfilename])
        return open(outfilename, 'rb').read()


@app.task(shared=False, queue='openmp')
def skymap_from_samples(samplefilecontents):
    """Generate multi-resolution fits file from samples."""
    with NamedTemporaryFile(content=samplefilecontents) as samplefile, \
            tempfile.TemporaryDirectory() as tmpdir, \
            handling_system_exit():
        ligo_skymap_from_samples.main(
            ['-j', '-o', tmpdir, samplefile.name])
        with open(os.path.join(tmpdir, 'skymap.fits'), 'rb') as f:
            return f.read()


def plot_bayes_factor(logb,
                      values=(1, 3, 5),
                      labels=('', 'strong', 'very strong'),
                      xlim=7, title=None, palette='RdYlBu'):
    """Visualize a Bayes factor as a `bullet graph`_.

    Make a bar chart of a log Bayes factor as compared to a set of subjective
    threshold values. By default, use the thresholds from
    Kass & Raftery (1995).

    .. _`bullet graph`: https://en.wikipedia.org/wiki/Bullet_graph

    Parameters
    ----------
    logb : float
        The natural logarithm of the Bayes factor.
    values : list
        A list of floating point values for human-friendly confidence levels.
    labels : list
        A list of string labels for human-friendly confidence levels.
    xlim : float
        Limits of plot (`-xlim` to `+xlim`).
    title : str
        Title for plot.
    palette : str
        Color palette.

    Returns
    -------
    fig : Matplotlib figure
    ax : Matplotlib axes

    Example
    -------
    .. plot::
        :alt: Example Bayes factor plot

        from gwcelery.tasks.skymaps import plot_bayes_factor
        plot_bayes_factor(6.3, title='GWCelery is awesome')

    """
    with plt.style.context('seaborn-notebook'):
        fig, ax = plt.subplots(figsize=(6, 1.7), tight_layout=True)
        ax.set_xlim(-xlim, xlim)
        ax.set_ylim(-0.5, 0.5)
        ax.set_yticks([])
        ax.set_title(title)
        ax.set_ylabel(r'$\ln\,B$', rotation=0,
                      rotation_mode='anchor',
                      ha='right', va='center')

        # Add human-friendly labels
        ticks = (*(-x for x in reversed(values)), 0, *values)
        ticklabels = (
            *(f'{s}\nevidence\nagainst'.strip() for s in reversed(labels)), '',
            *(f'{s}\nevidence\nfor'.strip() for s in labels))
        ax.set_xticks(ticks)
        ax.set_xticklabels(ticklabels)
        plt.setp(ax.get_xticklines(), visible=False)
        plt.setp(ax.get_xticklabels()[:len(ticks) // 2], ha='right')
        plt.setp(ax.get_xticklabels()[len(ticks) // 2:], ha='left')

        # Plot colored bands for confidence thresholds
        fmt = plt.FuncFormatter(lambda x, _: f'{x:+g}'.replace('+0', '0'))
        ax2 = ax.twiny()
        ax2.set_xlim(*ax.get_xlim())
        ax2.set_xticks(ticks)
        ax2.xaxis.set_major_formatter(fmt)
        levels = (-xlim, *ticks, xlim)
        colors = plt.get_cmap(palette)(np.arange(1, len(levels)) / len(levels))
        ax.barh(0, np.diff(levels), 1, levels[:-1],
                linewidth=plt.rcParams['xtick.major.width'],
                color=colors, edgecolor='white')

        # Plot bar for log Bayes factor value
        ax.barh(0, logb, 0.5, color='black',
                linewidth=plt.rcParams['xtick.major.width'],
                edgecolor='white')

        for ax_ in fig.axes:
            ax_.grid(False)
            for spine in ax_.spines.values():
                spine.set_visible(False)

    return fig, ax


@app.task(shared=False)
@closing_figures()
def plot_coherence(filecontents):
    """IGWN alert handler to plot the coherence Bayes factor.

    Parameters
    ----------
    contents : str, bytes
        The contents of the FITS file.

    Returns
    -------
    png : bytes
        The contents of a PNG file.

    Notes
    -----
    Under the hood, this just calls :meth:`plot_bayes_factor`.

    """
    # Explicitly use a non-interactive Matplotlib backend.
    plt.switch_backend('agg')

    with NamedTemporaryFile(content=filecontents) as fitsfile:
        header = fits.getheader(fitsfile, 1)
    try:
        logb = header['LOGBCI']
    except KeyError:
        raise Ignore('FITS file does not have a LOGBCI field')

    objid = header['OBJECT']
    logb_string = np.format_float_positional(logb, 1, trim='0', sign=True)
    fig, _ = plot_bayes_factor(
        logb, title=rf'Coherence of {objid} $[\ln\,B = {logb_string}]$')
    outfile = io.BytesIO()
    fig.savefig(outfile, format='png')
    return outfile.getvalue()


@igwn_alert.handler('superevent',
                    'mdc_superevent',
                    shared=False)
def handle_plot_coherence(alert):
    """IGWN alert handler to plot and upload a visualization of the coherence
    Bayes factor.

    Notes
    -----
    Under the hood, this just calls :meth:`plot_coherence`.

    """
    if alert['alert_type'] != 'log':
        return  # not for us
    if not alert['data']['filename'].endswith('.fits'):
        return  # not for us

    graceid = alert['uid']
    f = alert['data']['filename']
    v = alert['data']['file_version']
    fv = '{},{}'.format(f, v)

    (
        gracedb.download.s(fv, graceid)
        |
        plot_coherence.s()
        |
        gracedb.upload.s(
            f.replace('.fits', '.coherence.png'), graceid,
            message=(
                f'Bayes factor for coherence vs. incoherence of '
                f'<a href="/api/superevents/{graceid}/files/{fv}">'
                f'{fv}</a>'),
            tags=['sky_loc']
        )
    ).delay()
