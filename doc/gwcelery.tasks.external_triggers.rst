gwcelery.tasks.external_triggers module
---------------------------------------

This module listens to the `GCNs` from SNEWS and the Fermi, Swift, INTEGRAL,
and AGILE missions. It is also responsible for carrying out tasks related to
external trigger-gravitational wave coincidences, including looking for
temporal coincidences, creating combined GRB-GW sky localization probability
maps, and computing their joint temporal and spatio-temporal false alarm
rates.

There are two GCN and two LVAlert message handlers in the
`~gwcelery.tasks.external_triggers` module:

* :meth:`~gwcelery.tasks.external_triggers.handle_sn_gcn` is called for
  each SNEWS GCN.

* :meth:`~gwcelery.tasks.external_triggers.handle_grb_gcn` is called for
  each GRB GCN such as Fermi, Swift, INTEGRAL, and AGILE MCAL.
    
* :meth:`~gwcelery.tasks.external_triggers.handle_sn_lvalert` is called
  for each SNEWS external trigger and superevent LVAlert.

* :meth:`~gwcelery.tasks.external_triggers.handle_grb_lvalert` is called
  for each Fermi and Swift external trigger and superevent LVAlert.

Flow Chart
~~~~~~~~~~

.. digraph:: exttrig

    compound = true
    nodesep = 0.1
    ranksep = 0.1

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

    SNEWS_GCN [
        style="rounded"
        label="SNEWS GCN recieved"
    ]

    GRB_GCN [
        style="rounded"
        label="GRB\nGCN recieved"
    ]

    subgraph cluster_gcn_handle {
        href = "../gwcelery.tasks.external_triggers.html#gwcelery.tasks.external_triggers.handle_gcn"
        label = <<B><FONT face="monospace">handle_gcn</FONT></B>>

        Ignore_gcn [
            label="Ignore"
        ]

        Likely_noise [
            shape=diamond
            label="Is the event\nlikely non-astrophysical?"
        ]

        Event_exists_in_Gracedb [
            shape=diamond
            label="Does the event already\nexist in gracedb"
        ]

        Update_existing_event_in_gracedb [
            label="Update the existing\nevent in gracedb"
        ]

        Create_new_event_in_gracedb [
            label="Create a new event\nin gracedb"
        ]
  
        Grab_create_skymap [
            label="Grab and/or\ncreate external sky map"
        ]
    }

    SNEWS_GCN -> Likely_noise [
        lhead = cluster_gcn_handle
    ]

    GRB_GCN -> Likely_noise [
        lhead = cluster_gcn_handle
    ]

    Likely_noise -> Event_exists_in_Gracedb[label="no"]
    Likely_noise -> Ignore_gcn[label="yes"]
    Event_exists_in_Gracedb -> Update_existing_event_in_gracedb[label="yes"]
    Event_exists_in_Gracedb -> Create_new_event_in_gracedb[label="no"]
    Update_existing_event_in_gracedb -> Grab_create_skymap
    Create_new_event_in_gracedb -> Grab_create_skymap

    GRB_External_Trigger_or_Superevent_LVAlert [
        style="rounded"
        label="GRB external trigger or\nSuperevent LVAlert received"
    ]

    subgraph cluster_grb_lvalert_handle {
        href = "../gwcelery.tasks.external_triggers.html#gwcelery.tasks.external_triggers.handle_grb_lvalert"
        label = <<B><FONT face="monospace">handle_grb_lvalert</FONT></B>>

        Ignore [
            label="Ignore"
        ]

        Is_New_LVAlert [
            shape=diamond
            label="Is this a\nnew type LVAlert?"
        ]

        Is_Swift_Subthresh_LVAlert [
            shape=diamond
            label="Is this a\nSwift Targeted Subthreshold\nLVAlert?"
        ]

        Create_Swift_Skymap [
            label="Create Swift sky map"
        ]

        Is_Label_Exttrig_LVAlert [
            shape=diamond
            label="Is this a label type\nexternal event LVAlert?"
        ]

        Perform_Raven_Search [
            label="Perform Raven\ncoincidence search(es)"
        ]

        Does_Label_Launch_Pipeline [
            shape=diamond
            label="Does label complete the\nset indicating a coincidence and both\nsky maps are available?"
        ]
 
        Launch_Raven_Pipeline [
            label="Launch Raven\nPipeline"
        ]

        Does_Label_Launch_Combined_Skymaps [
            shape=diamond
            label="Does label complete the\nset indicating RAVEN alert and both\nsky maps are available?"
        ]

        Create_Combined_Skymap [
            label="Create combined GW-GRB\nsky map"
        ]

    }

    GRB_External_Trigger_or_Superevent_LVAlert -> Is_New_LVAlert [
        lhead = cluster_grb_lvalert_handle
    ]
    Is_New_LVAlert -> Is_Swift_Subthresh_LVAlert[label="yes"]
    Is_Swift_Subthresh_LVAlert -> Create_Swift_Skymap[label="yes"]
    Create_Swift_Skymap -> Perform_Raven_Search
    Is_Swift_Subthresh_LVAlert -> Perform_Raven_Search[label="no"]
    Is_New_LVAlert -> Is_Label_Exttrig_LVAlert[label="no"]
    Is_Label_Exttrig_LVAlert -> Does_Label_Launch_Pipeline[label="yes"]
    Is_Label_Exttrig_LVAlert -> Ignore[label="no"]
    Does_Label_Launch_Pipeline -> Launch_Raven_Pipeline[label="yes"]
    Does_Label_Launch_Pipeline -> Does_Label_Launch_Combined_Skymaps[label="no"]
    Launch_Raven_Pipeline -> Does_Label_Launch_Combined_Skymaps
    Does_Label_Launch_Combined_Skymaps -> Create_Combined_Skymap[label="yes"]
    Does_Label_Launch_Combined_Skymaps -> Ignore[label="no"]

    SNEWS_External_Trigger_or_Superevent_LVAlert [
        style="rounded"
        label="SNEWS external trigger or\nSuperevent LVAlert received"
    ]

    subgraph cluster_sn_lvalert_handle {
        href = "../gwcelery.tasks.external_triggers.html#gwcelery.tasks.external_triggers.handle_sn_lvalert"
        label = <<B><FONT face="monospace">handle_sn_lvalert</FONT></B>>

        ignore [
            label="Ignore"
        ]

        is_new_exttrig_lvalert [
            shape=diamond
            label="Is this a new type SNEWS\nexternal trigger LVAlert?"
        ]

        is_new_superevent_lvalert [
            shape=diamond
            label="Is this a new type\nsuperevent LVAlert?"
        ]

        perform_raven_search [
            label="Perform Raven\ncoincidence search"
        ]
    }

    SNEWS_External_Trigger_or_Superevent_LVAlert -> is_new_exttrig_lvalert [
        lhead = cluster_sn_lvalert_handle
    ]
    is_new_exttrig_lvalert -> perform_raven_search[label="yes"]
    is_new_exttrig_lvalert -> is_new_superevent_lvalert[label="no"]
    is_new_superevent_lvalert -> perform_raven_search[label="yes"]
    is_new_superevent_lvalert -> ignore[label="no"]


Tasks
~~~~~
.. automodule:: gwcelery.tasks.external_triggers
