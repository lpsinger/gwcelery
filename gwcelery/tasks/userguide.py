"""Send static VOEvents from the
:doc:`open alerts user guide <userguide:index>`."""
from astropy import time
from astropy import units as u
from astropy.utils import data
from celery.task import PeriodicTask
from celery.schedules import crontab
from lxml import etree

from ..import app
from . import gcn

URL = 'https://emfollow.docs.ligo.org/userguide/_static/MS181101ab-1-Preliminary.xml'  # noqa: E501


@app.task(base=PeriodicTask, shared=False, run_every=crontab(minute='*/15'))
def send_static_voevent():
    """Send the static example VOEvent from the user guide."""
    # Determine a unique, incrementing packet number.
    now = time.Time.now()
    start = time.Time('2018-11-01')
    num = str(int((now - start).to(u.minute).value // 15))

    # Read and parse the original VOEvent.
    with data.get_readable_fileobj(URL, encoding='binary') as f:
        xml = etree.parse(f)

    # Update packet number.
    root = xml.getroot()
    root.attrib['ivorn'] = root.attrib['ivorn'].replace(
        '1-Preliminary', '{}-Preliminary'.format(num))
    xml.find(".//Param[@name='Pkt_Ser_Num']").attrib['value'] = num

    # Send VOEvent.
    gcn.send.delay(etree.tostring(xml))
