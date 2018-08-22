gwcelery\.tasks\.orchestrator module
------------------------------------

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

Flow Chart
~~~~~~~~~~

The flow chart below illustrates the operation of these two tasks.

.. digraph:: orchestrator

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

            send_gcn [
                label = "Send preliminary\nGCN notice"
            ]

            circular [
                label = "Create GCN\ncircular draft"
            ]
        }
    }

    superevent -> orchestrator_timeout [lhead = cluster_handle_superevent]

    orchestrator_timeout
    -> get_preferred_event
    -> check_vectors
    -> dqv

    dqv -> copy_from_preferred_event [label = No, lhead = cluster_preliminary_alert]
    copy_from_preferred_event -> send_gcn -> circular

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

        source_classification [
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
    download_psd -> download_coinc_psd -> bayestar -> source_classification
    download_ranking_data -> download_coinc_ranking_data -> p_astro

Tasks
~~~~~

.. automodule:: gwcelery.tasks.orchestrator
