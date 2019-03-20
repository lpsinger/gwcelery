gwcelery.tasks.detchar module
-----------------------------

Flow Chart
~~~~~~~~~~

The flow chart below shows the decision process for the application of DQOK and DQV labels.

.. digraph:: detchar

    compound = true
    nodesep = 0.3
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

    superevent [
        label = "Superevent created/updated"
        style = rounded
    ]

    external [
        label = "External trigger"
        style = rounded
    ]

    subgraph cluster_check {
        href = "../gwcelery.tasks.detchar.html#gwcelery.tasks.detchar.check_vectors"
        label = <<B><FONT face="monospace">detchar check_vectors</FONT></B>>

        padding [
            label = "Apply padding before/after start/end time"
        ]

        {
            rank = same

            check_dq_inj [
                label = "Check DQ and INJ\nstates at all detectors"
            ]

            check_idq [
                label = "Check iDQ\nat H1 and L1"
            ]
        }

        post_gracedb [
            label = "Post results to\nGraceDB log"
        ]

        dq_bits_ok [
            label = "DQ bits ok \nat active detectors?"
            shape = diamond
        ]

        inj_found [
            label = "Injection(s) found \nat active detectors?"
            shape = diamond
        ]

        idq_threshold [
            label = "iDQ P(glitch)\nabove threshold?"
            shape = diamond
        ]

        dqok [
            label = "DQOK"
            style = filled
            fillcolor = "green"
        ]

        dqv [
            label = "DQV"
            style = filled
            fillcolor = "red"
        ]

        inj [
            label = "INJ"
            style = filled
            fillcolor = "lightblue"
        ]
    }

    superevent -> padding
    external -> padding
    padding -> check_dq_inj
    padding -> check_idq
    check_dq_inj -> dq_bits_ok
    check_dq_inj -> inj_found
    check_dq_inj -> post_gracedb
    check_idq -> post_gracedb
    check_idq -> idq_threshold
    dq_bits_ok -> dqok [label = " Yes "]
    dq_bits_ok -> dqv [label = " No "]
    inj_found -> inj [label = " Yes "]
    idq_threshold -> dqv [label = " Yes "]

.. automodule:: gwcelery.tasks.detchar
