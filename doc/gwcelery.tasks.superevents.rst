gwcelery\.tasks\.superevents module
-----------------------------------

`Superevents` are a new abstraction of gravitational-wave candidates
introduced in the third LIGO/Virgo observing (O3). Each superevent is
intended to represent a single astrophysical event. A superevent
consists of one or more event candidates, possibly from different
pipelines, that are neighbors in ``gpstime``. One event belonging
to the superevent is identified as the preferred event.

Below is the workflow and the decision of the preferred_event.

.. digraph:: superevent_manager

    size ="12,12";
    // define the nodes
    lvalert [shape=ellipse, style=filled, color=khaki];
    far_check [shape=box, orientation=45,
               label="FAR < threshold\n ?"]
    fetch_superevents [shape=box,
                       label="Fetch superevents nearby \n trigger gpstime from GraceDb"];
    associated_superevent [shape=box, orientation=45,
                           label="Event window in \n any superevent window?"];
    create_superevent [shape=box,
                       label="Create \n superevent"]
    add_to_superevent [shape=box,
                       label="Add to \n superevent"]
    group_tie [shape=box,
               label="Are the new event and \n preferred event groups same?",
               orientation=45]
    cbc_preferred [shape=box,
                   label="CBC is preferred"]
    cbc_burst [shape=box,
               label="Tie between CBC \n or Burst?", orientation=45]
    far_tie_breaker [shape=box, orientation=45,
                     label="FAR \n < \n preferred_event FAR?"]
    snr_tie_breaker [shape=box, orientation=45,
                     label="SNR \n > \n preferred_event SNR?"]
    set_preferred [shape=box,
                   label="Set as preferred event"]

    // draw the connections
    lvalert -> far_check [label="proceed if new \n type alert",
                          style=dotted];
    far_check -> fetch_superevents [style=dotted,
                                    label="Yes"];
    fetch_superevents -> associated_superevent;
    associated_superevent -> create_superevent [label="No",
                                                style=dotted];
    associated_superevent -> add_to_superevent [label="Yes",
                                                style=dotted];
    add_to_superevent -> group_tie;
    group_tie -> cbc_preferred [label="No", style=dotted];
    group_tie -> cbc_burst [label="Yes", style=dotted];
    cbc_burst -> snr_tie_breaker[label="CBC", style=dotted];
    cbc_burst -> far_tie_breaker[label="Burst", style=dotted];
    far_tie_breaker -> set_preferred [label="Yes", style=dotted];
    snr_tie_breaker -> set_preferred [label="Yes", style=dotted];

.. automodule:: gwcelery.tasks.superevents
