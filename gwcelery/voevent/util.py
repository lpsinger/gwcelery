"""VOEvent-related utilities."""
import ipaddress
import socket


def get_host_port(address):
    """Split a network address of the form ``host:port``.

    Parameters
    ----------
    network : str
        The network address.

    Returns
    -------
    host : str
        The hostname, or an empty string if missing.
    port : int, None
        The port number, or None if missing.
    """
    host, _, port = address.partition(':')
    return host, (int(port) if port else None)


def get_local_ivo(app):
    """Create an IVOID to identify this application in VOEvent Transport
    Protocol packets.

    Returns
    -------
    str
        A local IVOID composed of the machine's fully qualified domain name and
        the Celery application name (for example,
        `ivo://emfollow.ligo.caltech.edu/gwcelery`).
    """
    return 'ivo://{}/{}'.format(socket.getfqdn(), app.main)


def get_network(address):
    """Find the IP network prefix for a hostname or CIDR notation.

    Parameters
    ----------
    address : str
        A hostname, such as ``ligo.org``, or an IP address prefix in CIDR
        notation, such as ``127.0.0.0/8``.

    Returns
    -------
    ipaddress.IPv4Network
        An object representing the IP address prefix.
    """
    try:
        net = ipaddress.ip_network(address, strict=False)
    except ValueError:
        net = ipaddress.ip_network(socket.gethostbyname(address), strict=False)
    return net
