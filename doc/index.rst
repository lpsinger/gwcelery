GWCelery
========

GWCelery is a simple and reliable package for annotating and orchestrating
LIGO/Virgo alerts, built from widely used open source components. It is built
on the :doc:`Celery <celery:index>` distributed task queue (hence the name).
This is the design and reference manual for GWCelery.

GWCelery's responsibilities include:

1. Merging related candidates from multiple online LIGO/Virgo transient
   searches into "superevents"
2. Correlating LIGO/Virgo events with gamma-ray bursts, neutrinos,
   and supernovae
3. Launching automated follow-up analyses including data quality checks, rapid
   sky localization, automated parameter estimation, and source classification
4. Generating and sending preliminary machine-readable GCN notices
5. Sending updated GCN notices after awaiting human input
6. Automatically composing GCN Circulars

.. note::
   If you are a scientist, student, educator, or astronomy enthusiast looking
   for information about LIGO/Virgo alerts and low-latency data products, then
   please see our :doc:`LIGO/Virgo Public Alerts User Guide <userguide:index>`.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   quickstart
   design
   configuration
   htcondor
   monitoring
   gwcelery
   contributing
   deployment

.. toctree::
   :maxdepth: 1

   Git repository <http://git.ligo.org/emfollow/gwcelery>
   changes
   license

Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

GWCelery is open source and is licensed under the :doc:`GNU General Public
License v2 or later <license>`.
