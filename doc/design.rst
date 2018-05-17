Design and anatomy of GWCelery
==============================

Processes
---------

A complete deployment of GWCelery consists of the following processes:

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

4.  **General-Purpose Worker**

    A Celery worker that accepts most kinds of tasks.

5.  **OpenMP Worker**

    A Celery worker that has been configured to accept only computationally
    intensive tasks that use OpenMP parallelism. To route a task to the OpenMP
    worker, pass the keyword argument ``queue='openmp'`` to the ``@app.task``
    decorator when you declare it.

    There are currently two such tasks:
    :meth:`gwcelery.tasks.bayestar.localize` and
    :meth:`gwcelery.tasks.skymaps.plot_volume`.

6.  **VOEvent Queue**

    A Celery worker that is dedicated to sending VOEvents (has to be dedicated
    for technical reasons).

    There is only one such task: :meth:`gwcelery.tasks.voevent.send`.

Eternal Tasks
-------------

GWCelery has a couple long-running tasks that do not return because they have
to keep open a persistent connection with some external service. These tasks
are subclasses of :class:`~celery_eternal.EternalTask` or
:class:`~celery_eternal.EternalProcessTask`.

*  :meth:`gwcelery.tasks.voevent.listen`
*  :meth:`gwcelery.tasks.lvalert.listen`

Both of these run inside the general-purpose worker process described above.

.. _`Choosing a Broker`: http://docs.celeryproject.org/en/latest/getting-started/first-steps-with-celery.html#choosing-a-broker
.. _Redis: http://docs.celeryproject.org/en/latest/getting-started/brokers/redis.html#broker-redis
.. _`Periodic Tasks`: http://docs.celeryproject.org/en/latest/userguide/periodic-tasks.html
.. _Flower: http://flower.readthedocs.io/en/latest/
