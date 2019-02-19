gwcelery.tasks.external_triggers module
---------------------------------------

This module listens to the `GCNs` from SNEWS and the Fermi and Swift
missions. It is also responsible for carrying out tasks related to
external trigger-gravitational wave coincidences, including looking for
temporal coincidences, creating combined GRB-GW sky localization probability
maps, and computing their joint temporal and spatio-temporal false alarm
rates.

There are two GCN and two LVAlert message handlers in the
`~gwcelery.tasks.external_triggers` module:

* :meth:`~gwcelery.tasks.external_triggers.handle_sn_gcn` is called for
  each SNEWS GCN.

* :meth:`~gwcelery.tasks.external_triggers.handle_grb_gcn` is called for
  each Fermi and Swift GCN.
    
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

    Fermi_Swift_GCN [
        style="rounded"
        label="Fermi or Swift\nGCN recieved"
    ]

    subgraph cluster_gcn_handle {
        href = "../gwcelery.tasks.external_triggers.html#gwcelery.tasks.external_triggers.handle_gcn"
        label = <<B><FONT face="monospace">handle_gcn</FONT></B>>

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
    }

    SNEWS_GCN -> Event_exists_in_Gracedb [
        lhead = cluster_gcn_handle
    ]

    Fermi_Swift_GCN -> Event_exists_in_Gracedb [
        lhead = cluster_gcn_handle
    ]

    Event_exists_in_Gracedb -> Update_existing_event_in_gracedb[label="yes"]
    Event_exists_in_Gracedb -> Create_new_event_in_gracedb[label="no"]

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

        Is_New_ExtTrig_LVAlert [
            shape=diamond
            label="Is this a new type GRB\nexternal trigger LVAlert?"
        ]

        Is_New_Superevent_LVAlert [
            shape=diamond
            label="Is this a new type\nsuperevent LVAlert?"
        ]

        Is_Label_Superevent_LVAlert [
           shape=diamond
           label="Is this a label type\nsuperevent LVAlert?"
        ]

        Is_Label_EM_COINC [
            shape=diamond
            label="Is it an EM_COINC\nlabel?"
        ]

        Perform_Raven_Search [
            label="Perform Raven\ncoincidence search(es)"
        ]

        Create_Combined_Skymap [
            label="Create combined LVC-Fermi\nsky map"
        ]

        Calculate_Combined_FAR [
            label="Calculate FAR\n of GRB external\ntrigger-GW temporal\ncoincidence"
        ]

        Calculate_Combined_Spacetime_FAR [
            label="Calculate FAR\n of GRB external\ntrigger-GW space-time\ncoincidence"
        ]
    }

    GRB_External_Trigger_or_Superevent_LVAlert -> Is_New_ExtTrig_LVAlert [
        lhead = cluster_grb_lvalert_handle
    ]
    Is_New_ExtTrig_LVAlert -> Perform_Raven_Search[label="yes"]
    Is_New_ExtTrig_LVAlert -> Is_New_Superevent_LVAlert[label="no"]
    Is_New_Superevent_LVAlert -> Perform_Raven_Search[label="yes"]
    Is_New_Superevent_LVAlert -> Is_Label_Superevent_LVAlert[label="no"];
    Is_Label_Superevent_LVAlert -> Is_Label_EM_COINC[label="yes"];
    Is_Label_Superevent_LVAlert -> Ignore[label="no"];
    Is_Label_EM_COINC -> Create_Combined_Skymap[label="yes"];
    Create_Combined_Skymap -> Calculate_Combined_FAR
    Calculate_Combined_FAR -> Calculate_Combined_Spacetime_FAR
    Is_Label_EM_COINC -> Ignore[label="no"]

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
