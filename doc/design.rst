Design and anatomy of GWCelery
==============================

Processes
---------

A complete deployment of GWCelery (whether launched from the
:doc:`shell <quickstart>` or from :doc:`HTCondor <htcondor>`) consists
of several processes:

1.  **Message Broker**

    Routes and distributes Celery task messages and stores results of tasks for
    later retrieval. See `Choosing a Broker`_ in the Celery manual for more
    details. For technical reasons, we use a Redis_ broker.

2.  **Celery Beat**

    Scheduler for periodic tasks (the Celery equivalent of
    cron jobs). For more information, see `Periodic Tasks`_ in the Celery
    manual.

3.  **Monitoring Console** (optional)

    You can optionally run Flower_, a web monitoring console for Celery.

4.  **OpenMP Worker**

    A Celery worker that has been configured to accept only computationally
    intensive tasks that use OpenMP parallelism. To route a task to the OpenMP
    worker, pass the keyword argument ``queue='openmp'`` to the ``@app.task``
    decorator when you declare it.

    There are two tasks that run in the OpenMP queue:

    *  :meth:`gwcelery.tasks.bayestar.localize`
    *  :meth:`gwcelery.tasks.skymaps.plot_volume`

5.  **Superevent Worker**

    A Celery worker that is dedicated to serially process triggers from low
    latency pipelines and create/modify superevents in *GraceDb*. There is only
    one task that runs on the Superevent queue:

    *  :meth:`gwcelery.tasks.superevents.handle`

6.  **External Trigger Worker**

    A Celery worker that is dedicated to serially process external triggers from GRB
    alerts received from Fermi, Swift and neutrino alerts received from SNEWS 
    and create/modify external trigger events in *GraceDb*:

    *  :meth:`gwcelery.tasks.gcn.external_triggers.handle`

7.  **General-Purpose Worker**

    A Celery worker that accepts all other tasks.

Eternal tasks
-------------

GWCelery has a couple long-running tasks that do not return because they have
to keep open a persistent connection with some external service. These tasks
are subclasses of :class:`celery_eternal.EternalTask` or
:class:`celery_eternal.EternalProcessTask`.

*  :meth:`gwcelery.tasks.gcn.broker`
*  :meth:`gwcelery.tasks.gcn.listen`
*  :meth:`gwcelery.tasks.lvalert.listen`

Both of these run inside the general-purpose worker process described above,
and are automatically started (and restarted as necessary) by Celery Beat.

Handlers
--------

A recurring pattern in GWCelery is that an eternal task listens continuously to
a remote connection, receives packets of data over that connection, and
dispatches further handling to other tasks based on packet type.

A decorator is provided to register a function as a Celery task and also plug
it in as a handler for one or more packet types. This pattern is used for both
GCN notices and LVAlert message handlers.

GCN notices
~~~~~~~~~~~

GCN notice handler tasks are declared using the
:meth:`gwcelery.tasks.gcn.handler` decorator::

    import lxml.etree
    from gwcelery.tasks import gcn

    @gcn.handler(gcn.NoticeType.FERMI_GBM_GND_POS,
                 gcn.NoticeType.FERMI_GBM_FIN_POS)
    def handle_fermi(payload):
        root = lxml.etree.fromstring(payload)
        # do work here...

LVAlert messages
~~~~~~~~~~~~~~~~

LVAlert message handler tasks are declared using the
:meth:`gwcelery.tasks.lvalert.handler` decorator::

    from gwcelery.tasks import lvalert

    @lvalert.handler('cbc_gstlal',
                     'cbc_pycbc',
                     'cbc_mbtaonline')
    def handle_cbc(alert):
        # do work here...


.. _`Choosing a Broker`: http://docs.celeryproject.org/en/latest/getting-started/first-steps-with-celery.html#choosing-a-broker
.. _Redis: http://docs.celeryproject.org/en/latest/getting-started/brokers/redis.html#broker-redis
.. _`Periodic Tasks`: http://docs.celeryproject.org/en/latest/userguide/periodic-tasks.html
.. _Flower: http://flower.readthedocs.io/en/latest/
