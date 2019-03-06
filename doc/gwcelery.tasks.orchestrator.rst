gwcelery.tasks.orchestrator module
----------------------------------

This module implements the alert orchestrator, which responsible for the
vetting and annotation workflow to produce preliminary, initial, and update
alerts for gravitational-wave event candidates.

The orchestrator consists of two LVAlert message handlers:

* :meth:`~gwcelery.tasks.orchestrator.handle_superevent` is called for each
  superevent. It waits for a short duration of
  :obj:`~gwcelery.conf.orchestrator_timeout` seconds for the selection of the
  superevent by the :mod:`superevent manager <gwcelery.tasks.superevents>` to
  stabilize, then performs data quality checks. If the data quality checks
  pass, then it calls :meth:`~gwcelery.tasks.orchestrator.preliminary_alert` to
  copy annotations from the preferred event and send the preliminary GCN
  notice.

* :meth:`~gwcelery.tasks.orchestrator.handle_cbc_event` is called for each CBC
  event. It performs some CBC-specific annotations that depend closely on the
  CBC matched-filter parameters estimates and that might influence selection of
  the preferred event: rapid sky localization with BAYESTAR and rapid source
  classification.

  Note that there is no equivalent of this task for burst events because both
  burst searches (cWB, LIB) have integrated source localization and have no
  other annotations.

Preliminary Alerts
~~~~~~~~~~~~~~~~~~

The flow chart below illustrates the operation of these two tasks.

.. digraph:: preliminary_alert

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

    superevent [
        label = "LVAlert message\nfor new\nsuperevent"
        style = rounded
    ]

    subgraph cluster_handle_superevent {
        href = "../gwcelery.tasks.orchestrator.html#gwcelery.tasks.orchestrator.handle_superevent"
        label = <<B><FONT face="monospace">handle_superevent</FONT></B>>

        orchestrator_timeout [
            href = "../gwcelery.conf.html#gwcelery.conf.orchestrator_timeout"
            label = <Wait<BR/><B><FONT face="monospace">orchestrator_timeout</FONT></B><BR/>seconds>
        ]

        get_preferred_event [
            label = "Get preferred event"
        ]

        check_vectors [
            href = "../gwcelery.tasks.detchar.html#gwcelery.tasks.detchar.check_vectors"
            label = "Check state vectors"
        ]

        offline_event [
            label = "Offline event\n?"
            shape = diamond
        ]

        far_threshold [
            label = "N_trials * FAR \n < threshold?"
            shape = diamond
        ]

        dqv [
            label = "Vetoed by\nstate vectors?"
            shape = diamond
        ]

        subgraph cluster_preliminary_alert {
            href = "../gwcelery.tasks.orchestrator.html#gwcelery.tasks.orchestrator.preliminary_alert"
            label = <<B><FONT face="monospace">preliminary_alert</FONT></B>>

            copy_from_preferred_event [
                label = "Copy classification\n(if CBC) and\nsky map from\npreferred event"
            ]

            annotate_skymaps [
                label = "Make sky\nmap plots"
            ]

            send_gcn [
                label = "Send preliminary\nGCN notice"
            ]

            circular [
                label = "Create GCN\ncircular draft"
                shape = diamond
            ]
        }
    }

    superevent -> orchestrator_timeout [lhead = cluster_handle_superevent]

    orchestrator_timeout
    -> get_preferred_event
    -> check_vectors
    -> offline_event 

    offline_event -> far_threshold [label = No, lhead = prelim_gcn_checks]
    far_threshold -> dqv [label = Yes, lhead = prelim_gcn_checks]

    dqv -> copy_from_preferred_event [label = No, lhead = cluster_preliminary_alert]
    copy_from_preferred_event -> annotate_skymaps -> send_gcn -> circular

    cbc_event [
        label = "LVAlert for\nfile added\nto CBC event"
        style = rounded
    ]

    subgraph cluster_handle_cbc_event {
        href = "../gwcelery.tasks.orchestrator.html#gwcelery.tasks.orchestrator.handle_cbc_event"
        label = <<B><FONT face="monospace">handle_cbc_event</FONT></B>>

        {
            rank = same

            which_file [
                label = "What is the\nfilename?"
                shape = diamond
            ]

            download_psd [
                label = <Download<BR/><FONT face="monospace">psd.xml.gz</FONT>>
            ]
        }

        download_ranking_data [
            label = <Download<BR/><FONT face="monospace">ranking_data<BR/>.xml.gz</FONT>>
        ]

        download_coinc_psd [
            label = <Download<BR/><FONT face="monospace">coinc.xml</FONT>>
        ]

        download_coinc_ranking_data [
            label = <Download<BR/><FONT face="monospace">coinc.xml</FONT>>
        ]

        bayestar [
            href = "../gwcelery.tasks.bayestar.html#gwcelery.tasks.bayestar.localize"
            label = <Create<BR/><FONT face="monospace">bayestar<BR/>.fits.gz</FONT>>
        ]

        em_bright [
            href = "../gwcelery.tasks.em_bright.html#gwcelery.tasks.em_bright.classifier"
            label = <Create<BR/><FONT face="monospace">source_<BR/>classi<BR/>fication<BR/>.json</FONT>>
        ]

        p_astro [
            href = "../gwcelery.tasks.p_astro_gstlal.html#gwcelery.tasks.p_astro_gstlal.compute_p_astro"
            label = <Create<BR/><FONT face="monospace">p_astro<BR/>_gstlal.json</FONT>>
        ]
    }

    cbc_event -> which_file [lhead = cluster_handle_cbc_event]
    which_file -> download_psd [
        fontname = monospace
        label = "psd\n.xml\n.gz"
    ]
    which_file -> download_ranking_data [
        fontname = monospace
        label = "ranking_data.xml.gz"
    ]
    download_psd -> download_coinc_psd -> bayestar -> em_bright
    download_ranking_data -> download_coinc_ranking_data -> p_astro

Initial and Update Alerts
~~~~~~~~~~~~~~~~~~~~~~~~~

The :meth:`~gwcelery.tasks.initial_alert` and
:meth:`~gwcelery.tasks.update_alert` tasks create Initial and Update alerts
respectively. At the moment, there is no handler or user interface to trigger
these tasks, and they must be invoked manually (see
:ref:`monitoring:Command-Line Tools`). A flow chart for the initial alerts is
shown below; the flow chart for update alerts is the same.

.. digraph:: initial_alert

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

    subgraph cluster_initial_alert {
        href = "../gwcelery.tasks.orchestrator.html#gwcelery.tasks.orchestrator.initial_alert"
        label = <<B><FONT face="monospace">initial_alert</FONT></B>>

        annotate_skymaps [
            label = "If sky map provided,\nthen make sky map plots"
        ]

        send_gcn [
            label = "Send\nGCN notice"
        ]
    }

    annotate_skymaps -> send_gcn

Retraction Alerts
~~~~~~~~~~~~~~~~~

Likewise, the :meth:`~gwcelery.tasks.retraction_alert` task creates Retraction
alerts, and at the moment must be invoked manually. A flow chart is shown below.

.. digraph:: retraction_alert

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

    subgraph cluster_initial_alert {
        href = "../gwcelery.tasks.orchestrator.html#gwcelery.tasks.orchestrator.retraction_alert"
        label = <<B><FONT face="monospace">retraction_alert</FONT></B>>

        send_gcn [
            label = "Send\nGCN notice"
        ]
    }

Tasks
~~~~~

.. automodule:: gwcelery.tasks.orchestrator
