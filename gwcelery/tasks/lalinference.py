"""Source Parameter Estimation with LALInference."""
from distutils.spawn import find_executable
from distutils.dir_util import mkpath
import glob
import itertools
import json
import math
import os
import shutil
import subprocess
import tempfile
import urllib

from celery import group
from glue.lal import Cache
from gwdatafind import find_urls
from gwpy.timeseries import StateVector
import lal
import lalsimulation

from .. import app
from ..jinja import env
from . import condor
from . import gracedb
from . import skymaps


ini_name = 'online_pe.ini'

executables = {'datafind': 'gw_data_find',
               'mergeNSscript': 'lalinference_nest2pos',
               'mergeMCMCscript': 'cbcBayesMCMC2pos',
               'combinePTMCMCh5script': 'cbcBayesCombinePTMCMCh5s',
               'resultspage': 'cbcBayesPostProc',
               'segfind': 'ligolw_segment_query',
               'ligolw_print': 'ligolw_print',
               'coherencetest': 'lalinference_coherence_test',
               'lalinferencenest': 'lalinference_nest',
               'lalinferencemcmc': 'lalinference_mcmc',
               'lalinferencebambi': 'lalinference_bambi',
               'lalinferencedatadump': 'lalinference_datadump',
               'ligo-skymap-from-samples': 'ligo-skymap-from-samples',
               'ligo-skymap-plot': 'ligo-skymap-plot',
               'processareas': 'process_areas',
               'computeroqweights': 'lalinference_compute_roq_weights',
               'mpiwrapper': 'lalinference_mpi_wrapper',
               'gracedb': 'gracedb',
               'ppanalysis': 'cbcBayesPPAnalysis',
               'pos_to_sim_inspiral': 'cbcBayesPosToSimInspiral'}

flow = 20.0

# number of samples between end time of the data used for psd estimation and
# start time of data for PE
padding = 16

# default number of realizations used for PSD estimation
default_num_of_realizations = 32


def _ifos(event):
    """Return ifos"""
    return event['extra_attributes']['CoincInspiral']['ifos'].split(',')


def _chirplen(singleinspiral):
    """Return chirplen"""
    return lalsimulation.SimInspiralChirpTimeBound(
               flow,
               singleinspiral['mass1'] * lal.MSUN_SI,
               singleinspiral['mass2'] * lal.MSUN_SI,
               0.0, 0.0
           )


def _round_up_to_power_of_two(x):
    """Return smallest power of two exceeding x"""
    return 2**math.ceil(math.log(x, 2))


def _seglen(singleinspiraltable):
    """Return seglen"""
    return max([_round_up_to_power_of_two(max(4.0, _chirplen(sngl) + 2.0))
                for sngl in singleinspiraltable])


def _freq_dict(freq, ifos):
    """Return dictionary whose keys are ifos and items are frequencies"""
    return dict((ifo, freq) for ifo in ifos)


def _fstop(singleinspiral):
    """Return final frequency"""
    return lalsimulation.IMRPhenomDGetPeakFreq(
               singleinspiral['mass1'], singleinspiral['mass2'], 0.0, 0.0
           )


def _srate(singleinspiraltable):
    """Return srate we should use"""
    return _round_up_to_power_of_two(
               max([_fstop(sngl) for sngl in singleinspiraltable])
           ) * 2


def _start(trigtime, seglen, num_of_realizations):
    """Return gps start time

    Parameters
    ----------
    trigtime : float
        The time of target trigger
    seglen : int
        The length of the segment used to calculate overlap between data and
        waveform
    num_of_realizations : int
        The number of noise realizations used for PSD estimation

    Return
    ------
    start : float
        GPS start time of the whole data used for Parameter Estimation
    """
    return trigtime + 2 - seglen - padding - num_of_realizations * seglen


def _start_of_science_segment_for_one_ifo(start, trigtime, ifo, frametype):
    """Return gps start time of correctly calibrated and observing-intent data
    on the time when interferometers are locked or trigtime if no science data
    available. In detail, this function returns the last continuous data whose
    statevector's Bit 0 (HOFT_OK), 1 (OBSERVATION_INTENT) and 2
    (OBSERVATION_READY) are 1. Here it is assumed that data around trigtime
    satisfies these criterions since detection pipelines already checked it.

    Parameters
    ----------
    start : float
        GPS start time of the time window over which data is searched for.
    trigtime : float
        GPS time of a trigger
    ifo : str
    frametype : str

    Return
    ------
    start : float
        GPS start time of found science segment
    """
    # get gps start and end time of available data
    datacache = Cache.from_urls(find_urls(ifo[0], frametype, start, trigtime))
    # treat the case where nothing was found with gwdatafind
    try:
        available_segment = datacache.to_segmentlistdict()[ifo[0]][-1]
    except KeyError:
        return trigtime
    start = max(start, available_segment[0])

    # check whether data is calibrated correctly, observing-intent and taken
    # while the inferferometers are locked
    flag = StateVector.read(
               datacache, app.conf['state_vector_channel_names'][ifo],
               start=start, end=trigtime,
               bits=["HOFT_OK", "OBSERVATION_INTENT", "OBSERVATION_READY"]
           ).to_dqflags()
    # treat the case where no PE-ready data is available
    try:
        pe_segment = (flag['HOFT_OK'].active -
                      ~flag['OBSERVATION_INTENT'].active -
                      ~flag['OBSERVATION_READY'].active)[-1]
    except IndexError:
        return trigtime

    return pe_segment[0]


def _start_of_science_segment(trigtime, seglen, ifos, frametype_dict):
    """Calculate gps start time of ready-for-PE data with
    _start_end_of_science_segment for each ifo and return maximum of start time
    and minimum of end time
    """
    start = _start(trigtime, seglen, default_num_of_realizations)
    for ifo in ifos:
        start = _start_of_science_segment_for_one_ifo(
                    start, trigtime, ifo, frametype_dict[ifo]
                )
    return start


def _psdstart_psdlength(start, trigtime, seglen):
    """Return gps start time and length of data for PSD estimation as a list.
    Note that psdlength has to be seglen multiplied by an integer"""
    psdlength = \
        math.floor(trigtime + 2 - seglen - padding - start) // seglen * seglen
    return (trigtime + 2 - seglen - padding - psdlength, psdlength)


def _find_appropriate_frametype_psdstart_psdlength(
    trigtime, seglen, ifos, superevent_id=None
):
    """Return appropriate frametype, psdstart and psdlength. This function sets
    long enough psdlength first and shorten psdlength depending on whether data
    is available, correctly calibrated, observing-intent and taken while the
    interferometers are locked. This function first searches for low-latency
    frame data and, if they are not available, searches for high-latency frame
    data. If enough data is not found finally, raise exception and report
    failure to GraceDB.
    """
    # First search for low-latecy frame data
    frametype_dict = app.conf['low_latency_frame_types']
    start = _start_of_science_segment(
                trigtime, seglen, ifos, frametype_dict
            )
    start_threshold = _start(trigtime, seglen, 1)
    if start <= start_threshold:
        psdstart, psdlength = _psdstart_psdlength(start, trigtime, seglen)
        return frametype_dict, psdstart, psdlength

    # If part of low-latency data has already vanished, search for high-latency
    # frame data
    frametype_dict = app.conf['high_latency_frame_types']
    start = _start_of_science_segment(
                trigtime, seglen, ifos, frametype_dict
            )
    if start <= start_threshold:
        psdstart, psdlength = _psdstart_psdlength(start, trigtime, seglen)
        return frametype_dict, psdstart, psdlength
    else:
        if superevent_id is not None:
            gracedb.upload.delay(
                filecontents=None, filename=None,
                graceid=superevent_id,
                message='Available data is not long enough, and ' +
                        'Parameter Estimation will never start automatically.',
                tags='pe'
            )
        raise


@app.task(shared=False)
def prepare_ini(event, superevent_id=None):
    """Determine an appropriate PE settings for the target event and return ini
    file content
    """
    # Get template of .ini file
    ini_template = env.get_template('online_pe.jinja2')

    # Download event's info to determine PE settings
    singleinspiraltable = event['extra_attributes']['SingleInspiral']
    trigtime = event['gpstime']

    # fill out the ini template and return the resultant content
    ifos = _ifos(event)
    seglen = _seglen(singleinspiraltable)
    # FIXME: seglen here might not be actual seglen if ROQ is used
    frametypes, psdstart, psdlength = \
        _find_appropriate_frametype_psdstart_psdlength(
            trigtime, seglen, ifos, superevent_id
        )
    ini_settings = {
        'service_url': gracedb.client._service_url,
        'types': frametypes,
        'channels': app.conf['strain_channel_names'],
        'webdir': os.path.join(app.conf['pe_results_path'], event['graceid']),
        'paths': [{'name': name, 'path': find_executable(executable)}
                  for name, executable in executables.items()],
        'q': min([sngl['mass2'] / sngl['mass1']
                  for sngl in singleinspiraltable]),
        'ifos': ifos,
        'seglen': seglen,
        'flow': _freq_dict(flow, ifos),
        'srate': _srate(singleinspiraltable),
        'gps_start_time': psdstart - 1.0,  # to be smaller than psdstart
        'gps_end_time': trigtime + 3.0,  # to be larger than trigtime + 2.0
        'psd_start_time': psdstart,
        'psd_length': psdlength
    }
    return ini_template.render(ini_settings)


@app.task(shared=False)
def dag_prepare(rundir, ini_contents, preferred_event_id, superevent_id):
    """Create a Condor DAG to run LALInference on a given event.

    Parameters
    ----------
    rundir : str
        The path to a run directory where the DAG file exits
    ini_contents : str
        The content of online_pe.ini
    preferred_event_id : str
        The GraceDb ID of a target preferred event
    superevent_id : str
        The GraceDb ID of a target superevent

    Returns
    -------
    submit_file : str
        The path to the .sub file
    """
    # write down .ini file in the run directory
    path_to_ini = rundir + '/' + ini_name
    with open(path_to_ini, 'w') as f:
        f.write(ini_contents)

    # run lalinference_pipe
    gracedb.upload.delay(
        filecontents=None, filename=None, graceid=superevent_id,
        message='starting LALInference online parameter estimation',
        tags='pe'
    )
    try:
        subprocess.run(['lalinference_pipe', '--run-path', rundir,
                        '--gid', preferred_event_id, path_to_ini],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       check=True)
        subprocess.run(['condor_submit_dag', '-no_submit',
                        rundir + '/multidag.dag'],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       check=True)
    except subprocess.CalledProcessError as e:
        contents = b'args:\n' + json.dumps(e.args[1]).encode('utf-8') + \
                   b'\n\nstdout:\n' + e.stdout + b'\n\nstderr:\n' + e.stderr
        gracedb.upload.delay(
            filecontents=contents, filename='pe_dag.log',
            graceid=superevent_id,
            message='Failed to prepare DAG', tags='pe'
        )
        shutil.rmtree(rundir)
        raise

    return rundir + '/multidag.dag.condor.sub'


def _find_paths_from_name(directory, name):
    """Return the paths of files or directories with given name under the
    specfied directory

    Parameters
    ----------
    directory : string
        Name of directory under which the target file or directory is searched
        for.
    name : string
        Name of target files or directories

    Returns
    -------
    paths : generator
        Paths to the target files or directories
    """
    return glob.iglob(os.path.join(directory, '**', name), recursive=True)


@app.task(ignore_result=True, shared=False)
def job_error_notification(request, exc, traceback, superevent_id, rundir):
    """Upload notification when condor.submit terminates unexpectedly.

    Parameters
    ----------
    request : Context (placeholder)
        Task request variables
    exc : Exception
        Exception rased by condor.submit
    traceback : str (placeholder)
        Traceback message from a task
    superevent_id : str
        The GraceDb ID of a target superevent
    rundir : str
        The run directory for PE
    """
    if type(exc) is condor.JobAborted:
        gracedb.upload.delay(
            filecontents=None, filename=None, graceid=superevent_id,
            message='Job was aborted.', tags='pe'
        )
    elif type(exc) is condor.JobFailed:
        gracedb.upload.delay(
            filecontents=None, filename=None, graceid=superevent_id,
            message='Job failed.', tags='pe'
        )
    # Get paths to .log files
    paths_to_log = _find_paths_from_name(rundir, '*.log')
    # Get paths to .err files
    paths_to_err = _find_paths_from_name(rundir, '*.err')
    # Upload .log and .err files
    for path in itertools.chain(paths_to_log, paths_to_err):
        with open(path, 'rb') as f:
            contents = f.read()
        if contents:
            gracedb.upload.delay(
                filecontents=contents, filename=os.path.basename(path),
                graceid=superevent_id,
                message='Here is a log file for PE.',
                tags='pe'
            )


@app.task(ignore_result=True, shared=False)
def _upload_url(pe_results_path, graceid):
    """Upload url of a page containing all of the plots."""
    path_to_posplots, = _find_paths_from_name(pe_results_path, 'posplots.html')
    baseurl = urllib.parse.urljoin(
                  app.conf['pe_results_url'],
                  os.path.relpath(
                      path_to_posplots,
                      app.conf['pe_results_path']
                  )
              )
    gracedb.upload.delay(
        filecontents=None, filename=None, graceid=graceid,
        message=('LALInference online parameter estimation finished.'
                 '<a href={}>results</a>').format(baseurl),
        tags='pe'
    )


@app.task(ignore_result=True, shared=False)
def _get_result_contents(pe_results_path, filename):
    """Return the contents of a PE results file by reading it from the local
    filesystem.
    """
    path, = _find_paths_from_name(pe_results_path, filename)
    with open(path, 'rb') as f:
        contents = f.read()
    return contents


def _upload_result(pe_results_path, filename, graceid, message, tag):
    """Return a canvas to get the contents of a PE result file and upload it to
    GraceDb.
    """
    return _get_result_contents.si(pe_results_path, filename) | \
        gracedb.upload.s(filename, graceid, message, tag)


def _upload_skymap(pe_results_path, graceid):
    return _get_result_contents.si(pe_results_path, 'LALInference.fits') | \
        group(
            skymaps.annotate_fits('LALInference.fits',
                                  graceid, ['pe', 'sky_loc']),
            gracedb.upload.s('LALInference.fits', graceid,
                             'LALInference FITS sky map', ['pe', 'sky_loc'])
        )


@app.task(ignore_result=True, shared=False)
def clean_up(rundir):
    """Clean up a run directory.

    Parameters
    ----------
    rundir : str
        The path to a run directory where the DAG file exits
    """
    shutil.rmtree(rundir)


def dag_finished(rundir, preferred_event_id, superevent_id):
    """Upload PE results and clean up run directory

    Parameters
    ----------
    rundir : str
        The path to a run directory where the DAG file exits
    preferred_event_id : str
        The GraceDb ID of a target preferred event
    superevent_id : str
        The GraceDb ID of a target superevent

    Returns
    -------
    tasks : canvas
        The work-flow for uploading PE results
    """
    # get path to pe results
    pe_results_path = \
        os.path.join(app.conf['pe_results_path'], preferred_event_id)

    # FIXME: _upload_url.si has to be out of group for gracedb.create_label.si
    # to run
    return \
        _upload_url.si(pe_results_path, superevent_id) | \
        group(
            _upload_skymap(pe_results_path, superevent_id),
            _upload_result(
                pe_results_path, 'extrinsic.png', superevent_id,
                'Corner plot for extrinsic parameters', 'pe'
            ),
            _upload_result(
                pe_results_path, 'intrinsic.png', superevent_id,
                'Corner plot for intrinsic parameters', 'pe'
            ),
            _upload_result(
                pe_results_path, 'sourceFrame.png', superevent_id,
                'Corner plot for source frame parameters', 'pe'
            )
        ) | gracedb.create_label.si('PE_READY', superevent_id) | \
        clean_up.si(rundir)


@app.task(ignore_result=True, shared=False)
def start_pe(ini_contents, preferred_event_id, superevent_id):
    """Run LALInference on a given event.

    Parameters
    ----------
    ini_contents : str
        The content of online_pe.ini
    preferred_event_id : str
        The GraceDb ID of a target preferred event
    superevent_id : str
        The GraceDb ID of a target superevent
    """
    # make a run directory
    lalinference_dir = os.path.expanduser('~/.cache/lalinference')
    mkpath(lalinference_dir)
    rundir = tempfile.mkdtemp(dir=lalinference_dir)

    (
        dag_prepare.s(rundir, ini_contents, preferred_event_id, superevent_id)
        |
        condor.submit.s().on_error(
            job_error_notification.s(superevent_id, rundir)
        )
        |
        dag_finished(rundir, preferred_event_id, superevent_id)
    ).delay()
