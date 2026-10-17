"""Website monitor. Detects failure, retries, notifies. No auto-deploy."""
import sqlite3
import os
import time
import urllib.request
from datetime import datetime

import config

def _db():
    os.makedirs(os.path.dirname(config.AGENT_DB_PATH) or ".", exist_ok=True)
    c = sqlite3.connect(config.AGENT_DB_PATH)
    c.execute("""CREATE TABLE IF NOT EXISTS checks(
      id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, target TEXT,
      status TEXT, ms INTEGER, error TEXT)""")
    return c

def check(url, timeout=20, retries=1):
    import urllib.error
    for i in range(retries + 1):
        t0 = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Rayvice-Agent/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                ms = int((time.time() - t0) * 1000)
                _save(url, "UP", ms, f"HTTP {r.status}")
                return {"ok": True, "ms": ms, "status": r.status}
        except urllib.error.HTTPError as e:
            # Server responded = UP (even 404: path missing, not server dead).
            # Only 5xx = real problem.
            ms = int((time.time() - t0) * 1000)
            if e.code < 500:
                _save(url, "UP", ms, f"HTTP {e.code} (alive, path may not exist)")
                return {"ok": True, "ms": ms, "status": e.code}
            err = f"HTTP {e.code}"
            if i == retries:
                _save(url, "DOWN", ms, err)
                return {"ok": False, "error": err}
            time.sleep(2)
        except Exception as e:
            err = str(e)[:300]
            if i == retries:
                _save(url, "DOWN", int((time.time() - t0) * 1000), err)
                return {"ok": False, "error": err}
            time.sleep(2)

def _save(target, status, ms, error):
    c = _db()
    c.execute("INSERT INTO checks(ts,target,status,ms,error) VALUES(?,?,?,?,?)",
              (datetime.utcnow().isoformat() + "Z", target, status, ms, error[:500]))
    c.commit()
    c.close()

def check_all():
    return {
        "site": check(config.RAYVICE_SITE),
        "backend": check(config.RAYVICE_BACKEND + "/api", retries=1),
    }
