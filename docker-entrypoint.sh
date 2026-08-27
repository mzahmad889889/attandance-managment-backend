#!/bin/sh
# Wait for the database before starting (create_all runs at import time)
python - <<'EOF'
import os, time, sys
from sqlalchemy import create_engine, text

url = os.environ.get("DATABASE_URL", "mysql+pymysql://root:@localhost/attandance_management_system")
for attempt in range(30):
    try:
        engine = create_engine(url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("[ENTRYPOINT] Database is reachable.")
        sys.exit(0)
    except Exception as e:
        print(f"[ENTRYPOINT] Waiting for database ({attempt + 1}/30): {e}")
        time.sleep(2)
print("[ENTRYPOINT] Database never became reachable.", file=sys.stderr)
sys.exit(1)
EOF

exec gunicorn -w 2 -b 0.0.0.0:5000 --timeout 300 app:app
