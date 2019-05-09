Design and anatomy of GWCelery
==============================

Conceptual overview
-------------------

Several online gravitational-wave transient search pipelines (currently Gstlal,
PyCBC, cWB, and oLIB) upload candidates in real time to GraceDB, the central
database and web portal for low-latency LIGO/Virgo analyses. Whenever an event
is uploaded or altered, GraceDB pushes machine-readable notifications through
LVAlert, a pubsub system based on XMPP_.

The business logic for selecting and sending alerts to astronomers resides not
in GraceDB itself but in GWCelery. The role of GWCelery in the LIGO/Virgo alert
infrastructure is to drive the workflow of aggregating and annotating
gravitational-wave candidates and sending GCN Notices to astronomers.

GWCelery interacts with GraceDB by listening for LVAlert messages and making
REST API requests through the GraceDB client. GWCelery interacts with GCN by
listening for and sending GCN Notices using the Comet VOEvent broker.

The major subsystems of GWCelery are:

* the LVAlert listener
* the GraceDB client
* the GCN listener
* the GCN broker
* the Superevent Manager, which clusters and merges related candidates into
  "superevents"
* the External Trigger Manager, which correlates gravitational-wave events with
  GRB, neutrino, and supernova events
* the Orchestrator, which executes the per-event annotation workflow

Block diagram
-------------

Below is a diagram illustrating the conceptual relationships of these
subsystems. Nodes in the graph are hyperlinks to the relevant API
documentation.

.. digraph:: superevents

    compound = true
    splines = ortho

    node [
        fillcolor = white
        shape = box
        style = filled
        target = "_top"
    ]

    graph [
        labeljust = "left"
        style = filled
        target = "_top"
    ]

    gracedb [
        label = "GraceDB"
    ]

    lvalert [
        label = "LVAlert"
    ]

    {
        rank = source

        gstlal [
            label = "Gstlal\nSearch"
        ]

        pycbc [
            label = "PyCBC\nSearch"
        ]

        cwb [
            label = "cWB\nSearch"
        ]

        olib [
            label = "oLIB\nSearch"
        ]
    }

    subgraph cluster_gwcelery {
        label = "GWCelery"

        {
            rank = same

            lvalert_listener [
                href = "../gwcelery.tasks.lvalert.html"
                label = "LVAlert\nListener"
            ]

            superevent_manager [
                href = "../gwcelery.tasks.superevents.html"
                label = "Superevent\nManager"
            ]

            gracedb_client [
                href = "../gwcelery.tasks.gracedb.html"
                label = "GraceDB\nClient"
            ]
        }

        raven [
            href = "../gwcelery.tasks.external_triggers.html"
            label = "External\nTrigger\nManager"
        ]

        subgraph cluster_orchestrator {
            href = "../gwcelery.tasks.orchestrator.html"
            label = "Orchestrator"

            {
                rank = same

                detchar [
                    href = "../gwcelery.tasks.detchar.html"
                    label = "Detchar"
                ]

                bayestar [
                    href = "../gwcelery.tasks.bayestar.html"
                    label = "BAYESTAR"
                ]

                lalinference [
                    href = "../gwcelery.tasks.lalinference.html"
                    label = "LALInference"
                ]
            }

            {
                rank = same

                skymaps [
                    href = "../gwcelery.tasks.skymaps.html"
                    label = "Sky Map\nVisualization"
                ]

                classification [
                    label = "Source\nClassification"
                ]

                circulars [
                    href = "../gwcelery.tasks.circulars.html"
                    label = "Circular\nTemplates"
                ]
            }
        }

        {
            rank = same

            gcn_listener [
                href = "../gwcelery.tasks.gcn.html"
                label = "GCN\nListener"
            ]

            gcn_broker [
                html = "gwcelery.tasks.gcn.html"
                label = "GCN\nBroker"
            ]
        }
    }

    gcn [
        label = "GCN"
    ]

    {
        rank = sink

        astronomers [
            label = "Astronomers"
        ]
    }

    gstlal -> gracedb
    pycbc -> gracedb
    cwb -> gracedb
    olib -> gracedb

    gracedb -> lvalert
    lvalert -> lvalert_listener
    gracedb -> gracedb_client [dir=back]

    lvalert_listener -> superevent_manager
    lvalert_listener -> detchar [lhead=cluster_orchestrator]
    lvalert_listener -> raven

    superevent_manager -> gracedb_client
    lalinference -> gracedb_client [ltail=cluster_orchestrator]
    raven -> gracedb_client

    detchar -> bayestar [style=invis]
    bayestar -> lalinference [style=invis]

    detchar -> skymaps [style=invis]
    bayestar -> classification [style=invis]
    lalinference -> circulars [style=invis]

    skymaps -> classification [style=invis]
    classification -> circulars [style=invis]

    classification -> gcn_broker [ltail=cluster_orchestrator]
    classification -> gcn_listener [dir=back, ltail=cluster_orchestrator]

    superevent_manager -> raven [style=invis]
    raven -> detchar [style=invis]
    raven -> bayestar [style=invis]
    raven -> lalinference [style=invis]

    gcn_listener -> gcn [dir=back]
    gcn_broker -> gcn
    gcn -> astronomers
    gcn -> astronomers [dir=back]

Processes
---------

A complete deployment of GWCelery (whether launched from the
:doc:`shell <quickstart>` or from :doc:`HTCondor <htcondor>`) consists
of several processes:

1.  **Message Broker**

    Routes and distributes Celery task messages and stores results of tasks for
    later retrieval. See :ref:`celery:celerytut-broker` in the Celery manual
    for more details. For technical reasons, we use a :ref:`Redis
    <celery:broker-redis>` broker.

2.  **Celery Beat**

    Scheduler for periodic tasks (the Celery equivalent of cron jobs). For more
    information, see :ref:`celery:guide-beat` in the Celery manual.

3.  **Monitoring Console** (optional)

    You can optionally run :ref:`Flower <celery:monitoring-flower>`, a web
    monitoring console for Celery.

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
    latency pipelines and create/modify superevents in GraceDB. There is only
    one task that runs on the Superevent queue:

    *  :meth:`gwcelery.tasks.superevents.handle`

6.  **External Trigger Worker**

    A Celery worker that is dedicated to serially process external triggers from GRB
    alerts received from Fermi, Swift and neutrino alerts received from SNEWS 
    and create/modify external trigger events in GraceDB:

    *  :meth:`gwcelery.tasks.external_triggers.handle_gcn`

7.  **VOEvent Worker**

    A Celery worker that is dedicated to sending and receiving VOEvents. It
    runs an embedded instance of the :doc:`comet:index` VOEvent broker, which
    is started and stopped using a set of custom :doc:`Celery bootsteps
    <celery:userguide/extending>`. Note that the VOEvent worker must be started
    with the ``--pool=solo`` option so that tasks are executed in the same
    Python process that is running the VOEvent broker.

8.  **General-Purpose Worker**

    A Celery worker that accepts all other tasks.

9.  **Flask Web Application**

    A web application that provides forms to manually initiate certain tasks,
    including sending an update alert or creating a mock event.

Eternal tasks
-------------

GWCelery has a few long-running tasks that do not return because they have to
keep open a persistent connection with some external service. These tasks are
subclasses of :class:`celery_eternal.EternalTask` or
:class:`celery_eternal.EternalProcessTask`.

*  :meth:`gwcelery.tasks.lvalert.listen`

These tasks run inside the general-purpose worker process described above,
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
                     'cbc_spiir',
                     'cbc_pycbc',
                     'cbc_mbtaonline')
    def handle_cbc(alert):
        # do work here...

.. _PyGCN: https://pypi.org/project/pygcn/
.. _XMPP: https://xmpp.org
