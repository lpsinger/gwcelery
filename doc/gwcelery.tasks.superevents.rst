gwcelery.tasks.superevents module
---------------------------------

Superevents are an abstraction to unify gravitational-wave candidates from
multiple search pipelines. Each superevent is intended to represent a single
astrophysical event. A superevent consists of one or more event candidates,
possibly from different pipelines, that are neighbors in time. At any given
time, one event belonging to the superevent is identified as the *preferred
event*.

This module provides the Superevent Manager, an IGWN Alert handler that creates
and updates superevents whenever new events are uploaded to GraceDB. It also
checks whether the superevent qualifies to be sent out as a LIGO-Virgo
public alert.

Event candidates are only considered for membership in a superevent if their
false alarm rate is less than or equal to the value of the
:obj:`~gwcelery.conf.superevent_far_threshold` configuration setting.

Each superevent has a time window described by a central time ``t_0``, a start
time ``t_start``, and a end time ``t_end``. The central time ``t_0`` is just
the time of the preferred event. The start and end time are extended to
encompass all of the events that belong to the superevent (see
:meth:`~gwcelery.tasks.superevents.get_ts`).

The first candidate reported from a search pipeline creates a superevent, with it
being the preferred event. Subsequent candidate additions to the superevent may result
in a change of the superevent time window. The preferred event may also be updated
as more significant candidates are added. However, this will stop once a candidate
passing the public false alarm rate threshold (mentioned in
:obj:`~gwcelery.conf.preliminary_alert_far_threshold`) is added to the
superevent. At this point, the preferred event is frozen and an automatically
generated preliminary notice is sent with the data products of the preferred event.
Triggers could however still be added to the superevent as the preliminary alert
and the ensuing annotations are being processed. Once the preliminary alert
is dispatched to the GCN broker, the preferred event would be revised after
a wait time of :obj:`~gwcelery.conf.superevent_clean_up_timeout`, following which
a second automatic preliminary alert would be issued.

Selection of the preferred event
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When a new event is added to a superevent, it may or may not become the new
preferred event. The preferred event is selected by considering the following
factors in order to resolve any ties:

1.   **Completeness**: Would the event be complete, as determined by the
     function :meth:`~gwcelery.tasks.superevents.is_complete`,
     for sending an automated public alert?

2.   **Public FAR threshold**: Does the false alarm rate pass the false alarm
     rate threshold mentioned in :obj:`~gwcelery.conf.preliminary_alert_far_threshold`?

3.   **Search group**: Is it a CBC event or a burst event? CBC events takes
     precedence.

4.   **Number of detectors**: How many detectors contributed data to the event?
     For CBC events, events with triggers from more detectors take precedence.

5.   **Significance**: For CBC events, which has the highest SNR? For burst
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

    far_differs [
        label = "Does only\none event pass \n public FAR\nthreshold?"
        shape = diamond
    ]

    completeness_differs [
        label = "Is only\none event\ncomplete?"
        shape = diamond
    ]

    far_decides [
        label = "Select the\npublishable\nevent"
    ]

    completeness_decides [
        label = "Select the\ncomplete\nevent"
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

    detectors_differ [
        label = "Does one event\ninvolve more\ndetectors?"
        shape = diamond
    ]

    detectors_decide [
        label = "Select the events\nwith the greatest\nnumber of detectors"
    ]

    cbc_significance [
        label = "Select event\nwith the\nhighest SNR"
    ]

    burst_significance [
        label = "Select event\nwith the\nlowest FAR"
    ]

    completeness_differs -> completeness_decides [label = Yes]
    completeness_differs -> far_differs[label = No]
    far_differs -> far_decides [label = Yes]
    far_differs -> group_differs [label = No]
    group_differs -> group_decides [label = Yes]
    group_differs -> which_group [label = No]
    which_group -> detectors_differ [label = CBC]
    detectors_differ -> detectors_decide [label = Yes]
    detectors_differ -> cbc_significance [label = No]
    which_group -> burst_significance [label = Burst]

.. note::
    When a preferred event is assigned to a superevent, it may not
    be complete i.e., its data products may not have been computed yet.
    Once all the data products of the preferred event is ready, the
    ``EM_READY`` label is applied to the superevent.

    The preferred event is frozen once an event candidate passing the
    public false alarm rate threshold is added to the superevent.
    This is denoted by the application of the ``EM_Selected`` label
    on the superevent.

    When the preliminary alert has been dispatched to the GCN broker, the
    ``GCN_PRELIM_SENT`` label is applied to the superevent which is used
    to revise the preferred event and launch a second preliminary alert.

    The second preliminary is sent even if the preferred event stays unchanged
    after the revision. In this case, it contains the same content as the
    first preliminary alert.

    The application of ``ADVNO`` before the launching of the second preliminary
    alert stops the process. A retraction notice is sent instead.

Tasks
~~~~~

.. automodule:: gwcelery.tasks.superevents
