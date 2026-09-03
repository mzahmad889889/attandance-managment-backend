"""TLS settings for the MySQL connection.

DB_SSL selects how PyMySQL treats transport security:

  auto (default)  Negotiate TLS when the server offers it, plaintext otherwise.
                  This is PyMySQL's own behaviour and the right choice for a
                  correctly configured server, whichever way it is set up.
  required        Demand TLS, failing if the server does not offer it. Use when
                  the server runs with --require_secure_transport=ON. Certificate
                  verification is off, since MySQL presents a self-signed
                  certificate no CA can vouch for; the link is still encrypted and
                  never leaves the host's private Docker network.
  off             Force plaintext.

'required' is deliberately not the default. A server that demands secure transport
but does not advertise TLS support cannot be reached at all, and in that state
'required' turns the server's own error into a client-side one, which is harder to
read. Let the server speak for itself.
"""
import os
import ssl

_OFF = ('off', 'false', '0', 'no', 'disabled')
_REQUIRED = ('required', 'require', 'on', 'true', '1', 'yes')


def connect_args():
    """DBAPI connect arguments for the configured database."""
    mode = os.environ.get('DB_SSL', 'auto').strip().lower()

    if mode in _OFF:
        return {'ssl_disabled': True}

    if mode in _REQUIRED:
        ctx = ssl.create_default_context()
        # check_hostname must be cleared before verify_mode, or Python rejects the change.
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return {'ssl': ctx}

    return {}
