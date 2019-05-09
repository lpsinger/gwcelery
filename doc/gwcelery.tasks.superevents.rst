gwcelery.tasks.superevents module
---------------------------------

Superevents are an abstraction to unify gravitational-wave candidates from
multiple search pipelines. Each superevent is intended to represent a single
astrophysical event. A superevent consists of one or more event candidates,
possibly from different pipelines, that are neighbors in time. At any given
time, one event belonging to the superevent is identified as the *preferred
event*.

This module provides the Superevent Manager, an LVAlert handler that creates
and updates superevents whenever new events are uploaded to GraceDB.

Events are only considered for membership in a superevent if their false alarm
rate is less than or equal to the value of the
:obj:`~gwcelery.conf.superevent_far_threshold` configuration setting.

Each superevent has a time window described by a central time ``t_0``, a start
time ``t_start``, and a end time ``t_end``. The central time ``t_0`` is just
the time of the preferred event. The start and end time are extended to
encompass all of the events that belong to the superevent (see
:meth:`~gwcelery.tasks.superevents.get_ts`).

Selection of the preferred event
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When a new event is added to a superevent, it may or may not become the new
preferred event. The preferred event is selected by considering the following
factors in order to resolve any ties:

1.   **Publishability**: Would the event eligible, as determined by the
     function :meth:`~gwcelery.tasks.superevents.should_publish`, for sending
     an automated public alert?

2.   **Search group**: Is it a CBC event or a burst event? CBC events takes
     precendence.

3.   **Significance**: For CBC events, which has the highest SNR? For burst
     events, which has the lowest FAR?

The selection of the preferred event from a pair of events is illustrated by
the decision tree below.

.. digraph:: preferred_event

    compound = true
    nodesep = 0.1
    ranksep = 0.5

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

    should_publish_differs [
        label = "Is only\none event\npublishable?"
        shape = diamond
    ]

    should_publish_decides [
        label = "Select the\npublishable\nevent"
    ]

    group_differs [
        label = "Are the events\nfrom different\nsearch groups?"
        shape = diamond
    ]

    group_decides [
        label = "Select the\nCBC event"
    ]

    which_group [
        label = "From which\nsearch group are\nthe events?"
        shape = diamond
    ]

    cbc_significance [
        label = "Select event\nwith the\nhighest SNR"
    ]

    burst_significance [
        label = "Select event\nwith the\nlowest FAR"
    ]

    should_publish_differs -> should_publish_decides [label = Yes]
    should_publish_differs -> group_differs [label = No]
    group_differs -> group_decides [label = Yes]
    group_differs -> which_group [label = No]
    which_group -> cbc_significance [label = CBC]
    which_group -> burst_significance [label = Burst]

Tasks
~~~~~

.. automodule:: gwcelery.tasks.superevents
