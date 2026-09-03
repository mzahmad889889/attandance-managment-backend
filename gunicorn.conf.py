"""Gunicorn settings for the attendance API.

Threads matter more than workers here. The default sync worker serves one request at a
time, so a single slow call (a face-recognition frame, a stalled MySQL read) queued every
other request behind it, including logins, and the browser just spun. gthread keeps the
process count low (each process holds its own copy of the face model, so processes are
what cost memory) while letting several requests progress at once.
"""
import os
import threading

bind = '0.0.0.0:5000'
workers = int(os.environ.get('WEB_CONCURRENCY', '1'))
worker_class = 'gthread'
threads = int(os.environ.get('WEB_THREADS', '4'))

# The arbiter restarts a worker whose main loop stops heart-beating for this long. With
# gthread that loop keeps beating while request threads work, so this is a crash guard,
# not a cap on request duration; the DB timeouts in src/__init__.py bound stalled queries.
timeout = int(os.environ.get('WEB_TIMEOUT', '120'))
graceful_timeout = 30
keepalive = 5

# Access log to stdout with the request time: when the API stalls again, the last logged
# request (or the one missing from the log) is the culprit.
accesslog = '-'
access_log_format = '%(h)s "%(r)s" %(s)s %(b)s %(M)sms'
errorlog = '-'


def post_worker_init(worker):
    """Load the face model in the background so the first check-in doesn't stall the API."""
    if os.environ.get('FACE_WARMUP', '1').strip().lower() in ('0', 'false', 'no', 'off'):
        return
    from src.routes.face_routes import warm_engine
    threading.Thread(target=warm_engine, name='face-warmup', daemon=True).start()
