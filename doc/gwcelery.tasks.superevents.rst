gwcelery.tasks.superevents module
---------------------------------

`Superevents` are a new abstraction of gravitational-wave candidates
introduced in the third LIGO/Virgo observing (O3). Each superevent is
intended to represent a single astrophysical event. A superevent
consists of one or more event candidates, possibly from different
pipelines, that are neighbors in ``gpstime``. One event belonging
to the superevent is identified as the preferred event.

Flow Chart
~~~~~~~~~~

The flow chart below illustrates the decision process for selection of the
preferred event.

.. digraph:: superevents

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

    lvalert [
        label = "LVAlert\nmessage"
        style = rounded
    ]

    subgraph cluster_handle {
        href = "../gwcelery.tasks.superevents.html#gwcelery.tasks.superevents.handle"
        label = <<B><FONT face="monospace">handle</FONT></B>>

        far_check [
            label = "FAR <\nthreshold?"
            shape = diamond
        ]

        fetch_superevents [
            label = "Fetch superevents\nwith nearby trigger\ntimes from GraceDb"
        ]

        {
            rank = same

            associated_superevent [
                label = "Event intersects\nany superevent\nwindow?"
                shape = diamond
            ]

            create_superevent [
                label = "Create\nsuperevent"
            ]
        }

        {
            rank = same

            preferred_event_multi_ifo [
                label = "Preferred event\n#detectors > 1"
                shape = diamond

            ]

            new_event_multi_ifo [
               label = "New event\n#detectors > 1"
               shape = diamond
            ]
        }

        {
            rank = same

            d1 [
                label="New event\npreferred"
            ]

            d2 [
                shape=point
                margin = "3.20,0.05"
            ]
        }

        add_to_superevent [
            label = "Add to\nsuperevent"
        ]

        {
            rank = same

            group_tie [
                label = "New event group\n= preferred event\ngroup?"
                shape = diamond
            ]

            cbc_preferred [
                label = "CBC is\npreferred"
            ]
        }

        cbc_burst [
            label = "Tie between\nCBC or Burst?"
            shape = diamond
        ]

        far_tie_breaker [
            label = "FAR <\npreferred event\nFAR?"
            shape = diamond
        ]

        snr_tie_breaker [
            label = "SNR >\npreferred event\nSNR?"
            shape = diamond
        ]

        set_preferred [label = "Set as preferred event"]
    }

    lvalert -> far_check [
        label = "proceed if new\ntype alert"
        lhead = cluster_handle
    ]
    far_check -> fetch_superevents [label = Yes]
    fetch_superevents -> associated_superevent
    associated_superevent -> create_superevent [label = No]
    associated_superevent -> add_to_superevent [label = Yes]
    add_to_superevent -> preferred_event_multi_ifo
    add_to_superevent -> new_event_multi_ifo
    new_event_multi_ifo -> d1 [label = Yes]
    preferred_event_multi_ifo -> d1 [label = No]
    d1 -> set_preferred
    new_event_multi_ifo -> d2 [label = Yes]
    preferred_event_multi_ifo -> d2 [label = Yes]
    d2 -> group_tie

    group_tie -> cbc_preferred [label = No]
    group_tie -> cbc_burst [label = Yes]
    cbc_burst -> snr_tie_breaker [label = CBC]
    cbc_burst -> far_tie_breaker [label = Burst]
    far_tie_breaker -> set_preferred [label = Yes]
    snr_tie_breaker -> set_preferred [label = Yes]

Tasks
~~~~~

.. automodule:: gwcelery.tasks.superevents
