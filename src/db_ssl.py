"""TLS settings for the MySQL connection.

The managed MySQL runs with ``--require_secure_transport=ON``, so PyMySQL has to
negotiate TLS or the server rejects the connection outright with error 3159,
"Connections using insecure transport are prohibited". PyMySQL only attempts TLS
when an ssl parameter is passed, so we hand it an explicit context.

Certificate verification is off: MySQL presents its own auto-generated self-signed
certificate, which no CA can vouch for. The connection is still encrypted, which is
what require_secure_transport asks for, and it never leaves the host's private
Docker network.

Set DB_SSL=off for a local MySQL that does not speak TLS.
"""
import os
import ssl

_OFF = ('off', 'false', '0', 'no')


def connect_args():
    """DBAPI connect arguments for the configured database."""
    if os.environ.get('DB_SSL', 'on').strip().lower() in _OFF:
        return {}

    ctx = ssl.create_default_context()
    # check_hostname must be cleared before verify_mode, or Python rejects the change.
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return {'ssl': ctx}
