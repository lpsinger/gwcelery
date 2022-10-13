"""Create and upload external sky maps."""
from astropy import units as u
from astropy.coordinates import ICRS, SkyCoord
from astropy_healpix import HEALPix, pixel_resolution_to_nside
from celery import group
#  import astropy.utils.data
import numpy as np
from ligo.skymap.io import fits
from ligo.skymap.tool import ligo_skymap_combine
import gcn
import healpy as hp
import lxml.etree
import re
import ssl
import urllib

from ..import app
from . import gracedb
from . import skymaps
from ..util.cmdline import handling_system_exit
from ..util.tempfile import NamedTemporaryFile
from ..import _version


def create_combined_skymap(se_id, ext_id):
    """Creates and uploads the combined LVC-Fermi skymap.

    This also uploads the external trigger skymap to the external trigger
    GraceDB page.
    """
    se_skymap_filename = get_skymap_filename(se_id)
    ext_skymap_filename = get_skymap_filename(ext_id)
    new_skymap_filename = re.findall(r'(.*).fits.gz', se_skymap_filename)[0]

    #  FIXME: put download functions in canvas
    se_skymap = gracedb.download(se_skymap_filename, se_id)
    ext_skymap = gracedb.download(ext_skymap_filename, ext_id)
    message = 'Combined LVC-external sky map using {0} and {1}'.format(
        se_skymap_filename, ext_skymap_filename)
    message_png = (
        'Mollweide projection of <a href="/api/events/{graceid}/files/'
        '{filename}">{filename}</a>').format(
            graceid=se_id, filename=new_skymap_filename + '-ext.fits.gz')

    (
        combine_skymaps.si(se_skymap, ext_skymap)
        |
        group(
            gracedb.upload.s(new_skymap_filename + '-ext.fits.gz', se_id,
                             message, ['sky_loc', 'public']),

            skymaps.plot_allsky.s()
            |
            gracedb.upload.s(new_skymap_filename + '-ext.png', se_id,
                             message_png, ['sky_loc', 'ext_coinc', 'public'])
        )
    ).delay()


@app.task(autoretry_for=(ValueError,), retry_backoff=10,
          retry_backoff_max=600)
def get_skymap_filename(graceid):
    """Get the skymap fits filename.

    If not available, will try again 10 seconds later, then 20, then 40, etc.
    until up to 10 minutes after initial attempt.
    """
    gracedb_log = gracedb.get_log(graceid)
    if 'S' in graceid:
        for message in reversed(gracedb_log):
            filename = message['filename']
            if filename.endswith('.multiorder.fits'):
                return filename
    else:
        for message in reversed(gracedb_log):
            filename = message['filename']
            if (filename.endswith('.fits') or filename.endswith('.fit') or
                    filename.endswith('.fits.gz')):
                return filename
    raise ValueError('No skymap available for {0} yet.'.format(graceid))


@app.task(shared=False)
def combine_skymaps(skymap1filebytes, skymap2filebytes):
    """This task combines the two input skymaps, in this case the external
    trigger skymap and the LVC skymap and writes to a temporary output file. It
    then returns the contents of the file as a byte array.
    """
    with NamedTemporaryFile(mode='rb', suffix='.fits.gz') as combinedskymap, \
            NamedTemporaryFile(content=skymap1filebytes) as skymap1file, \
            NamedTemporaryFile(content=skymap2filebytes) as skymap2file, \
            handling_system_exit():
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
    """Returns the HEASARC fits file link."""
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
def get_external_skymap(link, search):
    """Download the Fermi sky map fits file and return the contents as a byte
    array. If GRB, will construct a HEASARC url, while if SubGRB, will use the
    link directly.

    If not available, will try again 10 seconds later, then 20, then 40, etc.
    until up to 10 minutes after initial attempt.
    """
    if search == 'GRB':
        # if Fermi GRB, determine final HEASARC link
        trigger_id = re.sub(r'.*\/(\D+?)(\d+)(\D+)\/.*', r'\2', link)
        skymap_name = 'glg_healpix_all_bn{0}_v00.fit'.format(trigger_id)
        skymap_link = link + skymap_name
    elif search == 'SubGRB':
        skymap_link = link
    #  FIXME: Under Anaconda on the LIGO Caltech computing cluster, Python
    #  (and curl, for that matter) fail to negotiate TLSv1.2 with
    #  heasarc.gsfc.nasa.gov
    context = ssl.create_default_context()
    context.options |= ssl.OP_NO_TLSv1_3
    #  return astropy.utils.data.get_file_contents(
    #      (skymap_link), encoding='binary', cache=False)
    return urllib.request.urlopen(skymap_link, context=context).read()


@app.task(autoretry_for=(urllib.error.HTTPError, urllib.error.URLError,),
          retry_backoff=10, retry_backoff_max=1200)
def get_upload_external_skymap(event, skymap_link=None):
    """If a Fermi sky map is not uploaded yet, tries to download one and upload
    to external event. If sky map is not available, passes so that this can be
    re-run the next time an update GCN notice is received. If GRB, will
    construct a HEASARC url, while if SubGRB, will use the link directly.
    """
    graceid = event['graceid']
    search = event['search']

    try:
        filename = get_skymap_filename(graceid)
        if 'glg_healpix_all_bn_v00.fit' in filename:
            return
    except ValueError:
        pass

    if search == 'GRB':
        external_skymap_canvas = (
            external_trigger_heasarc.si(graceid)
            |
            get_external_skymap.s(search)
        )
    elif search == 'SubGRB':
        external_skymap_canvas = get_external_skymap.si(skymap_link, search)

    skymap_filename = 'glg_healpix_all_bn_v00'

    message = (
        'Mollweide projection of <a href="/api/events/{graceid}/files/'
        '{filename}">{filename}</a>').format(
            graceid=graceid, filename=skymap_filename + '.fits')

    (
        external_skymap_canvas
        |
        group(
            gracedb.upload.s(
                skymap_filename + '.fits',
                graceid,
                'Official sky map from Fermi analysis.',
                ['sky_loc']),

            skymaps.plot_allsky.s()
            |
            gracedb.upload.s(skymap_filename + '.png',
                             graceid,
                             message,
                             ['sky_loc'])
        )
        |
        gracedb.create_label.si('EXT_SKYMAP_READY', graceid)
    ).delay()


def create_external_skymap(ra, dec, error, pipeline, notice_type=111):
    """Create a sky map, either a gaussian or a single
    pixel sky map, given an RA, dec, and error radius.

    If from Fermi, convolves the sky map with both a core and
    tail Gaussian and then sums these to account for systematic
    effects as measured in :doi:`10.1088/0067-0049/216/2/32`

    If from Swift, converts the error radius from that containing 90% of the
    credible region to ~68% (see description of Swift error
    here:`https://gcn.gsfc.nasa.gov/swift.html#tc7`)

    Parameters
    ----------
    ra : float
        right ascension in deg
    dec: float
        declination in deg
    error: float
        error radius in deg

    Returns
    -------
    skymap : numpy array
        sky map array

    """
    max_nside = 2048
    if error:
        # Correct 90% containment to 1-sigma for Swift
        if pipeline == 'Swift':
            error /= np.sqrt(-2 * np.log1p(-.9))
        error_radius = error * u.deg
        nside = pixel_resolution_to_nside(error_radius, round='up')
    else:
        nside = np.inf
    if nside >= max_nside:
        nside = max_nside

        #  Find the one pixel the event can localized to
        hpx = HEALPix(nside, 'ring', frame=ICRS())
        skymap = np.zeros(hpx.npix)
        ind = hpx.lonlat_to_healpix(ra * u.deg, dec * u.deg)
        skymap[ind] = 1.
    else:
        #  If larger error, create gaussian sky map
        hpx = HEALPix(nside, 'ring', frame=ICRS())
        ipix = np.arange(hpx.npix)

        #  Evaluate Gaussian.
        center = SkyCoord(ra * u.deg, dec * u.deg)
        distance = hpx.healpix_to_skycoord(ipix).separation(center)
        skymap = np.exp(-0.5 * np.square(distance / error_radius).to_value(
            u.dimensionless_unscaled))
        skymap /= skymap.sum()
    if pipeline == 'Fermi':
        # Correct for Fermi systematics based on recommendations from GBM team
        # Convolve with both a narrow core and wide tail Gaussian with error
        # radius determined by the scales respectively, each comprising a
        # fraction determined by the weights respectively
        if notice_type == gcn.NoticeType.FERMI_GBM_FLT_POS:
            # Flight notice
            # Values from first row of Table 7
            weights = [0.897, 0.103]
            scales = [7.52, 55.6]
        elif notice_type == gcn.NoticeType.FERMI_GBM_GND_POS:
            # Ground notice
            # Values from first row of Table 3
            weights = [0.804, 0.196]
            scales = [3.72, 13.7]
        elif notice_type == gcn.NoticeType.FERMI_GBM_FIN_POS:
            # Final notice
            # Values from second row of Table 3
            weights = [0.900, 0.100]
            scales = [3.71, 14.3]
        else:
            raise AssertionError(
                'Need to provide a supported Fermi notice type')
        skymap = sum(
            weight * hp.sphtfunc.smoothing(skymap, sigma=np.radians(scale))
            for weight, scale in zip(weights, scales))

    # Renormalize due to possible lack of precision
    # Enforce the skymap to be non-negative
    return np.abs(skymap) / np.abs(skymap).sum()


def write_to_fits(skymap, event, notice_type, notice_date):
    """Write external sky map fits file, populating the
    header with relevant info.

    Parameters
    ----------
    skymap : numpy array
        sky map array
    event : dict
        Dictionary of Swift external event

    Returns
    -------
    skymap fits : bytes array
        bytes array of sky map

    """
    notice_type_dict = {
        '53': 'INTEGRAL_WAKEUP',
        '54': 'INTEGRAL_REFINED',
        '55': 'INTEGRAL_OFFLINE',
        '60': 'SWIFT_BAT_GRB_ALERT',
        '61': 'SWIFT_BAT_GRB_POSITION',
        '105': 'AGILE_MCAL_ALERT',
        '110': 'FERMI_GBM_ALERT',
        '111': 'FERMI_GBM_FLT_POS',
        '112': 'FERMI_GBM_GND_POS',
        '115': 'FERMI_GBM_FINAL_POS',
        '131': 'FERMI_GBM_SUBTHRESHOLD'}

    if notice_type is None:
        msgtype = event['pipeline'] + '_LVK_TARGETED_SEARCH'
    else:
        msgtype = notice_type_dict[str(notice_type)]

    gcn_id = event['extra_attributes']['GRB']['trigger_id']
    with NamedTemporaryFile(suffix='.fits.gz') as f:
        fits.write_sky_map(f.name, skymap,
                           objid=gcn_id,
                           url=event['links']['self'],
                           instruments=event['pipeline'],
                           gps_time=event['gpstime'],
                           msgtype=msgtype,
                           msgdate=notice_date,
                           creator='gwcelery',
                           origin='LIGO-VIRGO-KAGRA',
                           vcs_version=_version.get_versions()['version'],
                           history='file only for internal use')
        with open(f.name, 'rb') as file:
            return file.read()


@app.task(shared=False)
def create_upload_external_skymap(event, notice_type, notice_date):
    """Create and upload external sky map using
    RA, dec, and error radius information.

    Parameters
    ----------
    event : dict
        Dictionary of Swift external event

    """
    graceid = event['graceid']
    skymap_filename = event['pipeline'].lower() + '_skymap.fits.gz'

    ra = event['extra_attributes']['GRB']['ra']
    dec = event['extra_attributes']['GRB']['dec']
    error = event['extra_attributes']['GRB']['error_radius']
    pipeline = event['pipeline']

    if not (ra or dec or error):
        # Don't create sky map if notice only contains zeros, lacking info
        return
    skymap = create_external_skymap(ra, dec, error, pipeline, notice_type)

    skymap_data = write_to_fits(skymap, event, notice_type, notice_date)

    message = (
        'Mollweide projection of <a href="/api/events/{graceid}/files/'
        '{filename}">{filename}</a>').format(
            graceid=graceid, filename=skymap_filename)

    (
        gracedb.upload.si(skymap_data,
                          skymap_filename,
                          graceid,
                          'Sky map created from GCN RA, dec, and error.',
                          ['sky_loc'])
        |
        skymaps.plot_allsky.si(skymap_data, ra=ra, dec=dec)
        |
        gracedb.upload.s(event['pipeline'].lower() + '_skymap.png',
                         graceid,
                         message,
                         ['sky_loc'])
        |
        gracedb.create_label.si('EXT_SKYMAP_READY', graceid)
    ).delay()
