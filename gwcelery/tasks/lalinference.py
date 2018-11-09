"""Source Parameter Estimation with LALInference."""
from distutils.spawn import find_executable
from distutils.dir_util import mkpath
import glob
import json
import os
import shutil
import subprocess
import tempfile

from celery import group

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


def _webdir(graceid):
    """Return webdir filled in .ini file"""
    return os.getenv('HOME') + '/public_html/online_pe/' + graceid


def _write_ini(rundir, graceid):
    """Write down .ini file in run directory and return path to .ini file"""
    # Get template of .ini file
    ini_template = env.get_template(ini_name)

    # Get service url, webdir and executables' paths filled in .ini file
    service_url = gracedb.client._service_url
    webdir = _webdir(graceid)
    executables_paths = [{'name': name, 'path': find_executable(executable)}
                         for name, executable in executables.items()]

    # Fill service-url, data types, data channels, webdir and
    # executables' paths in the template
    ini_contents = ini_template.render({'service_url': service_url,
                                        'types':
                                        json.dumps(app.conf['frame_types']),
                                        'channels':
                                        json.dumps(app.conf['channel_names']),
                                        'webdir': webdir,
                                        'paths': executables_paths})

    # write down .ini file in the run directory
    path_to_ini = rundir + '/' + ini_name
    with open(path_to_ini, 'w') as f:
        f.write(ini_contents)

    return path_to_ini


@app.task(shared=False)
def dag_prepare(rundir, download_id, upload_id):
    """Create a Condor DAG to run LALInference on a given event.

    Parameters
    ----------
    rundir : str
        The path to a run directory where the DAG file exits
    download_id : str
        The GraceDb ID of an event from which xml files are downloaded
    upload_id : str
        The GraceDb ID of an event to which results are uploaded

    Returns
    -------
    submit_file : str
        The path to the .sub file
    """
    # write down .ini file in the run directory
    path_to_ini = _write_ini(rundir, download_id)

    # run lalinference_pipe
    gracedb.upload(
        filecontents=None, filename=None, graceid=upload_id,
        message='starting LALInference online parameter estimation'
    )
    try:
        subprocess.check_call(['lalinference_pipe',
                               '--run-path', rundir,
                               '--gid', download_id,
                               path_to_ini])
        subprocess.check_call(['condor_submit_dag', '-no_submit',
                               rundir + '/multidag.dag'])
    except subprocess.CalledProcessError:
        gracedb.upload(
            filecontents=None, filename=None, graceid=upload_id,
            message='Failed to prepare DAG'
        )
        shutil.rmtree(rundir)
        raise

    return rundir + '/multidag.dag.condor.sub'


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
        gracedb.upload(
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


def dag_finished(rundir, download_id, upload_id):
    """Upload PE results and clean up run directory

    Parameters
    ----------
    rundir : str
        The path to a run directory where the DAG file exits
    download_id : str
        The GraceDb ID of an event from which xml files are downloaded
    upload_id : str
        The GraceDb ID of an event to which results are uploaded

    Returns
    -------
    tasks : canvas
        The work-flow for uploading PE results
    """
    # get webdir where the results are outputted
    webdir = _webdir(download_id)

    return group(
        gracedb.upload.si(
            filecontents=None, filename=None, graceid=upload_id,
            message='LALInference online parameter estimation finished.'
        ),
        upload_result.si(
            webdir, 'LALInference.fits.gz', upload_id,
            'LALInference FITS sky map', 'sky_loc'
        ),
        upload_result.si(
            webdir, 'extrinsic.png', upload_id,
            'Corner plot for extrinsic parameters', 'pe'
        ),
        upload_result.si(
            webdir, 'intrinsic.png', upload_id,
            'Corner plot for intrinsic parameters', 'pe'
        ),
        upload_result.si(
            webdir, 'sourceFrame.png', upload_id,
            'Corner plot for source frame parameters', 'pe'
        )
    ) | clean_up.si(rundir)


@app.task(ignore_result=True, shared=False)
def lalinference(download_id, upload_id):
    """Run LALInference on a given event.

    Parameters
    ----------
    download_id : str
        The GraceDb ID of an event from which xml files are downloaded
    upload_id : str
        The GraceDb ID of an event to which results are uploaded
    """
    # make a run directory
    lalinference_dir = os.path.expanduser('~/.cache/lalinference')
    mkpath(lalinference_dir)
    rundir = tempfile.mkdtemp(dir=lalinference_dir)

    (
        dag_prepare.s(rundir, download_id, upload_id)
        |
        condor.submit.s()
        |
        dag_finished(rundir, download_id, upload_id)
    ).delay()
