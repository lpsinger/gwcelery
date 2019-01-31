"""Source Parameter Estimation with LALInference."""
from distutils.spawn import find_executable
from distutils.dir_util import mkpath
import glob
import json
import math
import os
import shutil
import subprocess
import tempfile

from celery import group
import lal
import lalsimulation

from .. import app
from ..jinja import env
from . import condor
from . import gracedb


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


def _webdir(graceid):
    """Return webdir filled in .ini file"""
    return os.getenv('HOME') + '/public_html/online_pe/' + graceid


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


def _return_ini(event):
    """Determine an appropriate PE settings for the target event and return ini
    file content
    """
    # Get template of .ini file
    ini_template = env.get_template(ini_name)

    # Download event's info to determine PE settings
    singleinspiraltable = event['extra_attributes']['SingleInspiral']

    # fill out the ini template and return the resultant content
    ifos = _ifos(event)
    ini_settings = {
        'service_url': gracedb.client._service_url,
        'types': json.dumps(app.conf['frame_types']),
        'channels': json.dumps(app.conf['channel_names']),
        'webdir': _webdir(event['graceid']),
        'paths': [{'name': name, 'path': find_executable(executable)}
                  for name, executable in executables.items()],
        'q': min([sngl['mass2'] / sngl['mass1']
                  for sngl in singleinspiraltable]),
        'ifos': json.dumps(ifos),
        'seglen': str(_seglen(singleinspiraltable)),
        'flow': json.dumps(_freq_dict(flow, ifos)),
        'srate': str(_srate(singleinspiraltable))
    }
    return ini_template.render(ini_settings)


@app.task(shared=False)
def upload_ini(event, superevent_id):
    """Upload ini file and return its content

    Parameters
    ----------
    event : dict
        information on a target preferred event
    superevent_id : str
        The GraceDb ID of a target superevent
    """
    ini_contents = _return_ini(event)
    gracedb.upload.delay(
        filecontents=ini_contents, filename='online_pe.ini',
        graceid=superevent_id,
        message='This is an appropriate ini file for this event.',
        tags='pe'
    )
    return ini_contents


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


@app.task(ignore_result=True, shared=False)
def job_error_notification(request, exc, traceback, superevent_id):
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
    """
    if type(exc) is condor.JobAborted:
        gracedb.upload.delay(
            filecontents=None, filename=None, graceid=superevent_id,
            message='Job was aborted.', tags='pe'
        )
    elif type(exc) is condor.JobFailed:
        gracedb.upload.delay(
            filecontents=None, filename=None, graceid=superevent_id,
            message='Job failed', tags='pe'
        )


@app.task(ignore_result=True, shared=False)
def upload_result(webdir, filename, graceid, message, tag):
    """Upload a PE result

    Parameters
    ----------
    graceid : str
        The GraceDb ID.
    """
    paths = list(glob.iglob(webdir + '/**/' + filename, recursive=True))
    if len(paths) == 1:
        with open(paths[0], 'rb') as f:
            contents = f.read()
        gracedb.upload.delay(
            contents, filename,
            graceid, message, tag
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
    # get webdir where the results are outputted
    webdir = _webdir(preferred_event_id)

    return group(
        gracedb.upload.si(
            filecontents=None, filename=None, graceid=superevent_id,
            message='LALInference online parameter estimation finished.',
            tags='pe'
        ),
        upload_result.si(
            webdir, 'LALInference.fits.gz', superevent_id,
            'LALInference FITS sky map', ['pe', 'sky_loc']
        ),
        upload_result.si(
            webdir, 'extrinsic.png', superevent_id,
            'Corner plot for extrinsic parameters', 'pe'
        ),
        upload_result.si(
            webdir, 'intrinsic.png', superevent_id,
            'Corner plot for intrinsic parameters', 'pe'
        ),
        upload_result.si(
            webdir, 'sourceFrame.png', superevent_id,
            'Corner plot for source frame parameters', 'pe'
        )
    ) | clean_up.si(rundir)


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
        condor.submit.s().on_error(job_error_notification.s(superevent_id))
        |
        dag_finished(rundir, preferred_event_id, superevent_id)
    ).delay()
