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

5.  **VOEvent Worker**

    A Celery worker that is dedicated to sending VOEvents (has to be dedicated
    for technical reasons). There is only task that runs in the VOEvent queue:

    *  :meth:`gwcelery.tasks.gcn.send`

6.  **General-Purpose Worker**

    A Celery worker that accepts all other tasks.

Eternal tasks
-------------

GWCelery has a couple long-running tasks that do not return because they have
to keep open a persistent connection with some external service. These tasks
are subclasses of :class:`celery_eternal.EternalTask` or
:class:`celery_eternal.EternalProcessTask`.

*  :meth:`gwcelery.tasks.gcn.listen`
*  :meth:`gwcelery.tasks.lvalert.listen`

Both of these run inside the general-purpose worker process described above.

.. _`Choosing a Broker`: http://docs.celeryproject.org/en/latest/getting-started/first-steps-with-celery.html#choosing-a-broker
.. _Redis: http://docs.celeryproject.org/en/latest/getting-started/brokers/redis.html#broker-redis
.. _`Periodic Tasks`: http://docs.celeryproject.org/en/latest/userguide/periodic-tasks.html
.. _Flower: http://flower.readthedocs.io/en/latest/
