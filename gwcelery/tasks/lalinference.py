"""Source Parameter Estimation with LALInference."""
from distutils.spawn import find_executable
from distutils.dir_util import mkpath
import glob
import itertools
import json
import os
import shutil
import subprocess
import tempfile
import urllib

from celery import group
from ligo.gracedb.exceptions import HTTPError
from gwdatafind import find_urls

from .. import app
from ..jinja import env
from .core import ordered_group
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


def _data_exists(end, frametype_dict):
    """Check whether data at end time can be found with gwdatafind and return
    true it it is found.
    """
    return min(
        len(
            find_urls(ifo[0], frametype_dict[ifo], end, end + 1)
        ) for ifo in frametype_dict.keys()
    ) > 0


class NotEnoughData(Exception):
    """Raised if found data is not enough due to the latency of data
    transfer
    """


@app.task(bind=True, autoretry_for=(NotEnoughData, ), default_retry_delay=1,
          max_retries=86400, retry_backoff=True, shared=False)
def query_data(self, trigtime):
    """Continues to query data until it is found with gwdatafind and return
    frametypes for the data. If data is not found in 86400 seconds = 1 day,
    raise NotEnoughData.
    """
    end = trigtime + 2
    if _data_exists(end, app.conf['low_latency_frame_types']):
        return app.conf['low_latency_frame_types']
    elif _data_exists(end, app.conf['high_latency_frame_types']):
        return app.conf['high_latency_frame_types']
    else:
        raise NotEnoughData


@app.task(ignore_result=True, shared=False)
def upload_no_frame_files(request, exc, traceback, superevent_id):
    """Upload notification when no frame files are found.

    Parameters
    ----------
    request : Context (placeholder)
        Task request variables
    exc : Exception
        Exception rased by condor.submit
    traceback : str (placeholder)
        Traceback message from a task
    superevent_id : str
        The GraceDB ID of a target superevent
    """
    if isinstance(exc, NotEnoughData):
        gracedb.upload.delay(
            filecontents=None, filename=None,
            graceid=superevent_id,
            message='Frame files have not been found.',
            tags='pe'
        )


@app.task(shared=False)
def prepare_ini(frametype_dict, event, superevent_id=None):
    """Determine an appropriate PE settings for the target event and return ini
    file content
    """
    # Get template of .ini file
    ini_template = env.get_template('online_pe.jinja2')

    # fill out the ini template and return the resultant content
    singleinspiraltable = event['extra_attributes']['SingleInspiral']
    ini_settings = {
        'service_url': gracedb.client._service_url,
        'types': frametype_dict,
        'channels': app.conf['strain_channel_names'],
        'state_vector_channels': app.conf['state_vector_channel_names'],
        'webdir': os.path.join(app.conf['pe_results_path'], event['graceid']),
        'paths': [{'name': name, 'path': find_executable(executable)}
                  for name, executable in executables.items()],
        'q': min([sngl['mass2'] / sngl['mass1']
                  for sngl in singleinspiraltable]),
    }
    return ini_template.render(ini_settings)


def pre_pe_tasks(event, superevent_id):
    """Return canvas of tasks executed before parameter estimation starts"""
    return query_data.s(event['gpstime']).on_error(
        upload_no_frame_files.s(superevent_id)
    ) | prepare_ini.s(event, superevent_id)


@app.task(shared=False)
def dag_prepare(
    coinc_psd, ini_contents, rundir, superevent_id
):
    """Create a Condor DAG to run LALInference on a given event.

    Parameters
    ----------
    coinc_psd : tuple
        The tuple of the byte contents of ``coinc.xml`` and ``psd.xml.gz``
    ini_contents : str
        The content of online_pe.ini
    rundir : str
        The path to a run directory where the DAG file exits
    superevent_id : str
        The GraceDB ID of a target superevent

    Returns
    -------
    submit_file : str
        The path to the .sub file
    """
    coinc_contents, psd_contents = coinc_psd

    # write down coicn.xml in the run directory
    path_to_coinc = os.path.join(rundir, 'coinc.xml')
    with open(path_to_coinc, 'wb') as f:
        f.write(coinc_contents)

    # write down psd.xml.gz
    if psd_contents is not None:
        path_to_psd = os.path.join(rundir, 'psd.xml.gz')
        with open(path_to_psd, 'wb') as f:
            f.write(psd_contents)
        psd_arg = ['--psd', path_to_psd]
    else:
        psd_arg = []

    # write down .ini file in the run directory
    path_to_ini = rundir + '/' + ini_name
    with open(path_to_ini, 'w') as f:
        f.write(ini_contents)

    # run lalinference_pipe
    try:
        lalinference_arg = ['lalinference_pipe', '--run-path', rundir,
                            '--coinc', path_to_coinc, path_to_ini] + psd_arg
        subprocess.run(lalinference_arg, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, check=True)
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
        The GraceDB ID of a target superevent
    rundir : str
        The run directory for PE
    """
    if isinstance(exc, condor.JobAborted):
        gracedb.upload.delay(
            filecontents=None, filename=None, graceid=superevent_id,
            message='Job was aborted.', tags='pe'
        )
    elif isinstance(exc, condor.JobFailed):
        gracedb.upload.delay(
            filecontents=None, filename=None, graceid=superevent_id,
            message='Job failed.', tags='pe'
        )
    # Get paths to .log files, .err files, .out files
    paths_to_log = _find_paths_from_name(rundir, '*.log')
    paths_to_err = _find_paths_from_name(rundir, '*.err')
    paths_to_out = _find_paths_from_name(rundir, '*.out')
    # Upload .log and .err files
    for path in itertools.chain(paths_to_log, paths_to_err, paths_to_out):
        with open(path, 'rb') as f:
            contents = f.read()
        if contents:
            # put .log suffix in log file names so that users can directly
            # read the contents instead of downloading them when they click
            # file names
            gracedb.upload.delay(
                filecontents=contents,
                filename=os.path.basename(path) + '.log',
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
    GraceDB.
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
        The GraceDB ID of a target preferred event
    superevent_id : str
        The GraceDB ID of a target superevent

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
                pe_results_path, 'sourceFrame.png', superevent_id,
                'Corner plot for source frame parameters', 'pe'
            )
        ) | gracedb.create_label.si('PE_READY', superevent_id) | \
        clean_up.si(rundir)


@gracedb.task(shared=False)
def _download_psd(gid):
    """Download ``psd.xml.gz`` and return its content. If that file does not
    exist, return None.
    """
    try:
        return gracedb.download("psd.xml.gz", gid)
    except HTTPError:
        return None


@app.task(ignore_result=True, shared=False)
def start_pe(ini_contents, preferred_event_id, superevent_id):
    """Run LALInference on a given event.

    Parameters
    ----------
    ini_contents : str
        The content of online_pe.ini
    preferred_event_id : str
        The GraceDB ID of a target preferred event
    superevent_id : str
        The GraceDB ID of a target superevent
    """
    gracedb.upload.delay(
        filecontents=None, filename=None, graceid=superevent_id,
        message=('starting LALInference online parameter estimation '
                 'for {}').format(preferred_event_id),
        tags='pe'
    )

    # make a run directory
    lalinference_dir = os.path.expanduser('~/.cache/lalinference')
    mkpath(lalinference_dir)
    rundir = tempfile.mkdtemp(dir=lalinference_dir,
                              prefix='{}_'.format(superevent_id))
    # give permissions to read the files under the run directory so that PE
    # ROTA people can check the status of parameter estimation.
    os.chmod(rundir, 0o755)

    (
        ordered_group(
            gracedb.download.s('coinc.xml', preferred_event_id),
            _download_psd.s(preferred_event_id)
        )
        |
        dag_prepare.s(ini_contents, rundir, superevent_id)
        |
        condor.submit.s().on_error(
            job_error_notification.s(superevent_id, rundir)
        )
        |
        dag_finished(rundir, preferred_event_id, superevent_id)
    ).delay()
