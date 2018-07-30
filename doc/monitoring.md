# Monitoring

There are several options for monitoring GWCelery.

## Flower

[Flower](https://flower.readthedocs.io/) is a dashboard for monitoring Celery
tasks. To start Flower for monitoring during local development, run the
following command and then navigate to `http://localhost:5555/` in your
browser:

	$ gwcelery flower

To set up monitoring on a LIGO Data Grid cluster machine (e.g.
`emfollow.ligo.caltech.edu`) protected by LIGO.org authentication, start Flower
using the following command:

	$ gwcelery flower --url-prefix=~${USER}/gwcelery

add the following lines to the file `~/public_html/.htaccess`:

	RewriteEngine on
	RewriteRule ^gwcelery/?(.*)$ http://emfollow.ligo.caltech.edu:5555/$1 [P]

Some additional firewall configuration may be required.

![monitoring screenshot](_static/screenshot.png)

## Nagios

The [dashboard.ligo.org](https://dashboard.ligo.org/) and
[monitor.ligo.org](https://monitor.ligo.org/) services use
[Nagios](https://www.nagios.com) to monitor and report on the health of all of
the components of the low-latency analysis infrastructure.

GWCelery provides the command `gwcelery nagios` to check the status of the
application and provide a report in [the format that Nagios
expects](https://assets.nagios.com/downloads/nagioscore/docs/nagioscore/3/en/pluginapi.html).

You can run it manually from the command line:

    $ gwcelery nagios
    OK: GWCelery is running normally

To configure Nagios itself, see the [Nagios configuration
overview](https://assets.nagios.com/downloads/nagioscore/docs/nagioscore/4/en/config.html), or the [Nagios Remote Plugin Executor
(NRPE)](https://assets.nagios.com/downloads/nagioscore/docs/nrpe/NRPE.pdf) if
GWCelery and Nagios are running on different hosts.
