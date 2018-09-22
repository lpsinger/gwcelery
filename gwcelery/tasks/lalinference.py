"""Source Parameter Estimation with LALInference."""
from distutils.spawn import find_executable
from distutils.dir_util import mkpath
import glob
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

# types relates service_url to data type
types = {"https://gracedb.ligo.org/api/":
         "{'H1':'H1_llhoft','L1':'L1_llhoft','V1':'V1Online'}",
         "https://gracedb-playground.ligo.org/api/":
         "{'H1':'H1_O2_llhoft','L1':'L1_O2_llhoft','V1':'V1_O2_llhoft'}"}

# channels relates service_url to data channel
channels = {"https://gracedb.ligo.org/api/":
            "{'H1':'H1:GDS-CALIB_STRAIN'," +
            "'L1':'L1:GDS-CALIB_STRAIN'," +
            "'V1':'V1:Hrec_hoft_16384Hz'}",
            "https://gracedb-playground.ligo.org/api/":
            "{'H1':'H1:GDS-CALIB_STRAIN_O2Replay'," +
            "'L1':'L1:GDS-CALIB_STRAIN_O2Replay'," +
            "'V1':'V1:Hrec_hoft_16384Hz_O2Replay'}"}

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
                                        'types': types[service_url],
                                        'channels': channels[service_url],
                                        'webdir': webdir,
                                        'paths': executables_paths})

    # write down .ini file in the run directory
    path_to_ini = rundir + '/' + ini_name
    with open(path_to_ini, 'w') as f:
        f.write(ini_contents)

    return path_to_ini


@app.task(shared=False)
def dag_prepare(rundir, graceid):
    """Create a Condor DAG to run LALInference on a given event.

    Parameters
    ----------
    rundir : str
        The path to a run directory where the DAG file exits.
    graceid : str
        The GraceDb ID.

    Returns
    -------
    submit_file : str
        The path to the .sub file
    """
    # write down .ini file in the run directory
    path_to_ini = _write_ini(rundir, graceid)

    # run lalinference_pipe
    gracedb.upload(
        filecontents=None, filename=None, graceid=graceid,
        message='starting LALInference online parameter estimation'
    )
    try:
        subprocess.check_call(['lalinference_pipe',
                               '--run-path', rundir,
                               '--gid', graceid,
                               path_to_ini])
        subprocess.check_call(['condor_submit_dag', '-no_submit',
                               rundir + '/multidag.dag'])
    except subprocess.CalledProcessError:
        gracedb.upload(
            filecontents=None, filename=None, graceid=graceid,
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
        The path to a run directory where the DAG file exits.
    """
    shutil.rmtree(rundir)


def dag_finished(rundir, graceid):
    """Upload PE results and clean up run directory

    Parameters
    ----------
    graceid : str
        The GraceDb ID.

    Returns
    -------
    tasks : canvas
        The work-flow for uploading PE results
    """
    # get webdir where the results are outputted
    webdir = _webdir(graceid)

    return group(
        gracedb.upload.si(
            filecontents=None, filename=None, graceid=graceid,
            message='LALInference online parameter estimation finished.'
        ),
        upload_result.si(
            webdir, 'LALInference.fits.gz', graceid,
            'LALInference FITS sky map', 'sky_loc'
        ),
        upload_result.si(
            webdir, 'extrinsic.png', graceid,
            'Corner plot for extrinsic parameters', 'pe'
        ),
        upload_result.si(
            webdir, 'intrinsic.png', graceid,
            'Corner plot for intrinsic parameters', 'pe'
        ),
        upload_result.si(
            webdir, 'sourceFrame.png', graceid,
            'Corner plot for source frame parameters', 'pe'
        )
    ) | clean_up.si(rundir)


@app.task(ignore_result=True, shared=False)
def lalinference(graceid):
    """Run LALInference on a given event.

    Parameters
    ----------
    graceid : str
        The GraceDb ID.
    """
    # make a run directory
    lalinference_dir = os.path.expanduser('~/.cache/lalinference')
    mkpath(lalinference_dir)
    rundir = tempfile.mkdtemp(dir=lalinference_dir)

    (
        dag_prepare.s(rundir, graceid)
        |
        condor.submit.s()
        |
        dag_finished(rundir, graceid)
    ).delay()
