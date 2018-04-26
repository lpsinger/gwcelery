"""Communication with GraceDB."""
from ligo.gracedb import rest

from ..celery import app


@app.task(shared=False)
def create_event(filecontents, search, pipeline, group, service):
    client = rest.GraceDb(service)
    response = client.createEvent(group=group, pipeline=pipeline,
                                  filename='initial.data', search=search,
                                  filecontents=filecontents)
    return response.json()['graceid']


@app.task(ignore_result=True, shared=False)
def create_tag(tag, n, graceid, service):
    rest.GraceDb(service).createTag(graceid, n, tag)


@app.task(shared=False)
def download(filename, graceid, service):
    """Download a file from GraceDB."""
    return rest.GraceDb(service).files(graceid, filename, raw=True).read()


@app.task(shared=False)
def get_log(graceid, service):
    return rest.GraceDb(service).logs(graceid).json()['log']


@app.task(ignore_result=True, shared=False)
def upload(filecontents, filename, graceid, service, message, tags):
    """Upload a file to GraceDB."""
    rest.GraceDb(service).writeLog(
        graceid, message, filename, filecontents, tags)
