"""Definitions of custom :doc:`Celery signals <celery:userguide/signals>`
related to emails.

These signals allow us to keep the VOEvent validation code decoupled from the
email client itself.
"""
from celery.utils.dispatch import Signal

email_received = Signal(
    name='email_received', providing_args=('rfc822',))
"""Fired whenever an email message is received.

Parameters
----------
rfc822 : bytes
    The :rfc:`822` contents of the message.

Examples
--------

Register an email listener like this::

    import email
    import email.policy

    @email_received.connect
    def on_email_received(rfc822, **kwargs):
        # Parse the RFC822 email.
        message = email.message_from_bytes(rfc822, policy=email.policy.default)
        # Print some of the message headers.
        print('Subject:', message['Subject'])
        print('From:', message['From'])
        # Print the plain-text message body.
        body = message.get_body(['plain']).get_content()
        print(body)
"""
