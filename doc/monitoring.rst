Monitoring
==========

There are several options for monitoring GWCelery.

Flower
------

Flower_ is a dashboard for monitoring Celery tasks. To start Flower for
monitoring during local development, run the following command and then
navigate to http://localhost:5555/ in your browser:

	$ gwcelery flower

To set up monitoring on a LIGO Data Grid cluster machine (e.g.
``emfollow.ligo.caltech.edu``) protected by LIGO.org authentication, start
Flower using the following command::

	$ gwcelery flower --url-prefix=~${USER}/gwcelery

add the following lines to the file ``~/public_html/.htaccess``::

	RewriteEngine on
	RewriteRule ^gwcelery/?(.*)$ http://emfollow.ligo.caltech.edu:5555/$1 [P]

Some additional firewall configuration may be required.

.. figure: screenshot.png
   :alt: Screenshot of Flower

Nagios
------

The dashboard.ligo.org_ and monitor.ligo.org_ services use Nagios_ to monitor
and report on the health of all of the components of the low-latency analysis
infrastructure.

GWCelery provides the command ``gwcelery nagios`` to check the status of the
application and provide a report in `the format that Nagios expects`_.

You can run it manually from the command line::

    $ gwcelery nagios
    OK: GWCelery is running normally

To configure Nagios itself, see the `Nagios configuration overview`_, or if
GWCelery and Nagios are running on different hosts, the `Nagios Remote Plugin
Executor (NRPE) documentation`_

.. _Flower: https://flower.readthedocs.io/
.. _dashboard.ligo.org: https://dashboard.ligo.org/
.. _monitor.ligo.org: https://monitor.ligo.org/
.. _Nagios: https://www.nagios.com
.. _the format that Nagios expects: https://assets.nagios.com/downloads/nagioscore/docs/nagioscore/3/en/pluginapi.html
.. _Nagios configuration overview: https://assets.nagios.com/downloads/nagioscore/docs/nagioscore/4/en/config.html
.. _Nagios Remote Plugin Executor (NRPE) documentation: https://assets.nagios.com/downloads/nagioscore/docs/nrpe/NRPE.pdf
