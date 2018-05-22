"""Communication with GraceDB."""
from ligo.gracedb import rest
from celery.local import PromiseProxy

from ..celery import app

# Defer initializing the GraceDb REST client until it is needed,
# because if the user lacks valid credentials, then the API will
# raise an exception as soon as it is instantiated---which would
# otherwise make it impossible to import this module without first
# logging in.
client = PromiseProxy(rest.GraceDb,
                      ('https://' + app.conf.gracedb_host + '/api/',))


@app.task(shared=False)
def create_event(filecontents, search, pipeline, group):
    """Create an event in GraceDb."""
    response = client.createEvent(group=group, pipeline=pipeline,
                                  filename='initial.data', search=search,
                                  filecontents=filecontents)
    return response.json()['graceid']


@app.task(ignore_result=True, shared=False)
def create_tag(tag, n, graceid):
    """Create a tag in GraceDb."""
    client.createTag(graceid, n, tag)


@app.task(shared=False)
def download(filename, graceid):
    """Download a file from GraceDB."""
    return client.files(graceid, filename, raw=True).read()


@app.task(shared=False)
def get_log(graceid):
    """Get all log messages for an event in GraceDb."""
    return client.logs(graceid).json()['log']


@app.task(ignore_result=True, shared=False)
def upload(filecontents, filename, graceid, message, tags=()):
    """Upload a file to GraceDB."""
    client.writeLog(graceid, message, filename, filecontents, tags)
