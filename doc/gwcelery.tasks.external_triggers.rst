gwcelery.tasks.external_triggers module
---------------------------------------

This module listens to the `GCNs` from SNEWS and the Fermi, Swift, INTEGRAL,
and AGILE missions. It is also responsible for carrying out tasks related to
external trigger-gravitational wave coincidences, including looking for
temporal coincidences, creating combined GRB-GW sky localization probability
maps, and computing their joint temporal and spatio-temporal false alarm
rates.

There are two GCN and two IGWN Alert message handlers in the
`~gwcelery.tasks.external_triggers` module:

* :meth:`~gwcelery.tasks.external_triggers.handle_snews_gcn` is called for
  each SNEWS GCN.

* :meth:`~gwcelery.tasks.external_triggers.handle_grb_gcn` is called for
  each GRB GCN such as Fermi, Swift, INTEGRAL, and AGILE MCAL.
    
* :meth:`~gwcelery.tasks.external_triggers.handle_snews_igwn_alert` is called
  for each SNEWS external trigger and superevent IGWN Alert.

* :meth:`~gwcelery.tasks.external_triggers.handle_grb_igwn_alert` is called
  for each Fermi and Swift external trigger and superevent IGWN Alert.

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

    GRB_External_Trigger_or_Superevent_IGWN_Alert [
        style="rounded"
        label="GRB external trigger or\nSuperevent IGWN Alert received"
    ]

    subgraph cluster_grb_igwn_alert_handle {
        href = "../gwcelery.tasks.external_triggers.html#gwcelery.tasks.external_triggers.handle_grb_igwn_alert"
        label = <<B><FONT face="monospace">handle_grb_igwn_alert</FONT></B>>

        Ignore [
            label="Ignore"
        ]

        Is_New_IGWN_Alert [
            shape=diamond
            label="Is this a\nnew type IGWN Alert?"
        ]

        Is_Swift_Subthresh_IGWN_Alert [
            shape=diamond
            label="Is this a\nSwift Targeted Subthreshold\nIGWN Alert?"
        ]

        Create_Swift_Skymap [
            label="Create Swift sky map"
        ]

        Is_Label_Exttrig_IGWN_Alert [
            shape=diamond
            label="Is this a label type\nexternal event IGWN Alert?"
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

    GRB_External_Trigger_or_Superevent_IGWN_Alert -> Is_New_IGWN_Alert [
        lhead = cluster_grb_igwn_alert_handle
    ]
    Is_New_IGWN_Alert -> Is_Swift_Subthresh_IGWN_Alert[label="yes"]
    Is_Swift_Subthresh_IGWN_Alert -> Create_Swift_Skymap[label="yes"]
    Create_Swift_Skymap -> Perform_Raven_Search
    Is_Swift_Subthresh_IGWN_Alert -> Perform_Raven_Search[label="no"]
    Is_New_IGWN_Alert -> Is_Label_Exttrig_IGWN_Alert[label="no"]
    Is_Label_Exttrig_IGWN_Alert -> Does_Label_Launch_Pipeline[label="yes"]
    Is_Label_Exttrig_IGWN_Alert -> Ignore[label="no"]
    Does_Label_Launch_Pipeline -> Launch_Raven_Pipeline[label="yes"]
    Does_Label_Launch_Pipeline -> Does_Label_Launch_Combined_Skymaps[label="no"]
    Launch_Raven_Pipeline -> Does_Label_Launch_Combined_Skymaps
    Does_Label_Launch_Combined_Skymaps -> Create_Combined_Skymap[label="yes"]
    Does_Label_Launch_Combined_Skymaps -> Ignore[label="no"]

    SNEWS_External_Trigger_or_Superevent_IGWN_Alert [
        style="rounded"
        label="SNEWS external trigger or\nSuperevent IGWN_Alert received"
    ]

    subgraph cluster_snews_igwn_alert_handle {
        href = "../gwcelery.tasks.external_triggers.html#gwcelery.tasks.external_triggers.handle_snews_igwn_alert"
        label = <<B><FONT face="monospace">handle_snews_igwn_alert</FONT></B>>

        ignore [
            label="Ignore"
        ]

        is_new_exttrig_igwn_alert [
            shape=diamond
            label="Is this a new type SNEWS\nexternal trigger IGWN Alert?"
        ]

        is_new_superevent_igwn_alert [
            shape=diamond
            label="Is this a new type\nsuperevent IGWN Alert?"
        ]

        perform_raven_search [
            label="Perform Raven\ncoincidence search"
        ]
    }

    SNEWS_External_Trigger_or_Superevent_IGWN_Alert -> is_new_exttrig_igwn_alert [
        lhead = cluster_snews_igwn_alert_handle
    ]
    is_new_exttrig_igwn_alert -> perform_raven_search[label="yes"]
    is_new_exttrig_igwn_alert -> is_new_superevent_igwn_alert[label="no"]
    is_new_superevent_igwn_alert -> perform_raven_search[label="yes"]
    is_new_superevent_igwn_alert -> ignore[label="no"]


Tasks
~~~~~
.. automodule:: gwcelery.tasks.external_triggers
