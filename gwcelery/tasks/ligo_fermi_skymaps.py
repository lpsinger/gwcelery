"""Create and upload LVC-Fermi sky maps."""
import re
import urllib

from celery import group
from ligo.skymap.tool import ligo_skymap_combine
import astropy.utils.data
import lxml.etree

from . import gracedb
from ..import app
from ..util.tempfile import NamedTemporaryFile


def create_combined_skymap(graceid):
    """Creates and uploads the combined LVC-Fermi skymap. This also
    uploads the external trigger skymap to the external trigger GraceDB
    page."""
    preferred_skymap = get_preferred_skymap(graceid)
    message = 'Combined LVC-Fermi sky map using {0}.'.format(preferred_skymap)
    new_skymap = re.findall(r'(.*).fits', preferred_skymap)[0]+'-gbm.fits.gz'
    external_trigger_id = external_trigger(graceid)
    return (external_trigger_heasarc.s(external_trigger_id) |
            get_external_skymap.s() |
            group(
                combine_skymaps.s(gracedb.download(preferred_skymap,
                                                   graceid)) |
                gracedb.upload.s(
                    new_skymap, graceid, message, ['sky_loc', 'public']),

                gracedb.upload.s('glg_healpix_all_bn_v00.fit',
                                 external_trigger_id,
                                 'Sky map from HEASARC.',
                                 ['sky_loc', 'public']))
            )


@app.task(autoretry_for=(ValueError,), retry_backoff=10,
          retry_backoff_max=600)
def get_preferred_skymap(graceid):
    """Get the LVC skymap fits filename.
    If not available, will try again 10 seconds later, then 20,
    then 40, etc. until up to 10 minutes after initial attempt."""
    gracedb_log = gracedb.get_log(graceid)
    for message in reversed(gracedb_log):
        comment = message['comment']
        filename = message['filename']
        if (filename.endswith('.fits.gz') or filename.endswith('.fits')) and \
                'copied' in comment:
            return filename
    raise ValueError('No skymap available for {0} yet.'.format(graceid))


@app.task(shared=False)
def combine_skymaps(skymap1filebytes, skymap2filebytes):
    """This task combines the two input skymaps, in this case the external
    trigger skymap and the LVC skymap and writes to a temporary
    output file. It then returns the contents of the file as a byte array."""
    with NamedTemporaryFile(mode='rb', suffix='.fits.gz') as combinedskymap, \
            NamedTemporaryFile(content=skymap1filebytes) as skymap1file, \
            NamedTemporaryFile(content=skymap2filebytes) as skymap2file:
        ligo_skymap_combine.main([skymap1file.name,
                                  skymap2file.name, combinedskymap.name])
        return combinedskymap.read()


@app.task(shared=False)
def external_trigger(graceid):
    """Returns the associated external trigger GraceDB ID."""
    em_events = gracedb.get_superevent(graceid)['em_events']
    if len(em_events):
        for exttrig in em_events:
            if gracedb.get_event(exttrig)['search'] == 'GRB':
                return exttrig
    raise ValueError('No associated GRB EM event(s) for {0}.'.format(graceid))


@app.task(shared=False)
def external_trigger_heasarc(external_id):
    """Returns the HEASARC fits file link"""
    gracedb_log = gracedb.get_log(external_id)
    for message in gracedb_log:
        if 'Original Data' in message['comment']:
            filename = message['filename']
            xmlfile = gracedb.download(urllib.parse.quote(filename),
                                       external_id)
            root = lxml.etree.fromstring(xmlfile)
            heasarc_url = root.find('./What/Param[@name="LightCurve_URL"]'
                                    ).attrib['value']
            return re.sub(r'quicklook(.*)', 'current/', heasarc_url)
    raise ValueError('Not able to retrieve HEASARC link for {0}.'.format(
        external_id))


@app.task(autoretry_for=(urllib.error.HTTPError,), retry_backoff=10,
          retry_backoff_max=600)
def get_external_skymap(heasarc_link):
    """Download the Fermi sky map fits file and return the contents as a
       byte array.
       If not available, will try again 10 seconds later, then 20,
       then 40, etc. until up to 10 minutes after initial attempt."""
    trigger_id = re.sub(r'.*\/(\D+?)(\d+)(\D+)\/.*', r'\2', heasarc_link)
    skymap_name = 'glg_healpix_all_bn{0}_v00.fit'.format(trigger_id)
    skymap_link = heasarc_link + skymap_name
    return astropy.utils.data.get_file_contents(
        (skymap_link), encoding='binary', cache=False)
