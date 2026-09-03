#!/bin/sh
set -e

# Give the database a moment to come up, but never block startup on it. Exiting here
# makes an unreachable database indistinguishable from a broken container: the proxy
# just returns 502 and the real error is buried in container logs. Starting anyway
# means GET /api/health reports the actual reason over HTTP.
python - <<'EOF' || echo "[ENTRYPOINT] Starting anyway — GET /api/health will report the database error."
import os, sys, time
from sqlalchemy import create_engine, text
from src.db_ssl import connect_args

url = os.environ.get("DATABASE_URL", "mysql+pymysql://root:@localhost/attandance_management_system")
for attempt in range(15):
    try:
        engine = create_engine(url, connect_args=connect_args())
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("[ENTRYPOINT] Database is reachable.")
        sys.exit(0)
    except Exception as e:
        print(f"[ENTRYPOINT] Waiting for database ({attempt + 1}/15): {e}")
        time.sleep(2)
print("[ENTRYPOINT] Database never became reachable.", file=sys.stderr)
sys.exit(1)
EOF

# Worker class, thread count, timeouts and the face-model warm-up live in gunicorn.conf.py.
# Each worker process loads its own copy of the InsightFace model, so raise WEB_CONCURRENCY
# only on a host with memory to spare; WEB_THREADS is the cheap way to add concurrency.
exec gunicorn -c gunicorn.conf.py app:app
