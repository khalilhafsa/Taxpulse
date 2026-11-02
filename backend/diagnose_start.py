"""Start-up check used by diagnose.bat: imports the app and runs its start-up once, printing any error."""
import os
import traceback

os.environ.setdefault("SCHEDULER", "false")
try:
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        print("health:", c.get("/api/health").json())
    print("START-UP OK")
except Exception:
    traceback.print_exc()
