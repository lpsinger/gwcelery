from ligo.gracedb.rest import GraceDb

from ..celery import app


@app.task
def download(filename, graceid, service):
    """Download a file from GraceDB."""
    return GraceDb(service).files(graceid, filename, raw=True).read()


@app.task(ignore_result=True)
def upload(filecontents, filename, graceid, service, message, tags):
    """Upload a file to GraceDB."""
    GraceDb(service).writeLog(graceid, message, filename, filecontents, tags)
