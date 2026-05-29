"""
Barcode Scanner — License Server
Local:    python app.py  (or run.bat)
GCE/prod: gunicorn app:app  — see .env.example for required env vars
"""

import sqlite3
import os
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect, url_for

app = Flask(__name__)
app.secret_key   = os.environ.get("SECRET_KEY", "dev-secret-change-in-prod")
ADMIN_PASSWORD   = os.environ.get("ADMIN_PASSWORD", "admin123")
API_KEY          = os.environ.get("API_KEY", "")
DB_PATH          = os.environ.get("DATABASE_PATH") or \
                   os.path.join(os.path.dirname(__file__), "devices.db")


# Needed when running behind nginx — makes url_for() generate correct URLs
# even when nginx is stripping a path prefix (e.g. /barcode-scanner/)
class _ReverseProxied:
    def __init__(self, wsgi_app):
        self.app = wsgi_app

    def __call__(self, environ, start_response):
        prefix = environ.pop("HTTP_X_SCRIPT_NAME", "")
        if prefix:
            environ["SCRIPT_NAME"] = prefix
            path = environ.get("PATH_INFO", "")
            if path.startswith(prefix):
                environ["PATH_INFO"] = path[len(prefix):]
        scheme = environ.get("HTTP_X_FORWARDED_PROTO", "")
        if scheme:
            environ["wsgi.url_scheme"] = scheme
        return self.app(environ, start_response)

app.wsgi_app = _ReverseProxied(app.wsgi_app)


# ── Database ──────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True) if os.path.dirname(DB_PATH) else None
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                device_code  TEXT    UNIQUE NOT NULL,
                device_name  TEXT    NOT NULL DEFAULT 'Unnamed Device',
                status       TEXT    NOT NULL DEFAULT 'active',
                activated_at TEXT,
                revoked_at   TEXT,
                last_seen    TEXT,
                notes        TEXT
            )
        """)
        conn.commit()


# ── Auth ──────────────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("index"))
        error = "Incorrect password"
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ── Admin Web UI ──────────────────────────────────────────────────────────────

@app.route("/")
@login_required
def index():
    with get_db() as conn:
        devices = conn.execute(
            "SELECT * FROM devices ORDER BY activated_at DESC"
        ).fetchall()
    total   = len(devices)
    active  = sum(1 for d in devices if d["status"] == "active")
    revoked = total - active
    return render_template("index.html", devices=devices,
                           total=total, active=active, revoked=revoked)


@app.route("/activate", methods=["POST"])
@login_required
def activate():
    code  = request.form.get("device_code", "").strip().upper()
    name  = request.form.get("device_name", "").strip() or "Unnamed Device"
    notes = request.form.get("notes", "").strip()
    if not code:
        return redirect(url_for("index"))

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_db() as conn:
        conn.execute("""
            INSERT INTO devices (device_code, device_name, status, activated_at, notes)
            VALUES (?, ?, 'active', ?, ?)
            ON CONFLICT(device_code) DO UPDATE SET
                device_name  = excluded.device_name,
                status       = 'active',
                activated_at = ?,
                revoked_at   = NULL,
                notes        = excluded.notes
        """, (code, name, now, notes, now))
        conn.commit()
    return redirect(url_for("index"))


@app.route("/revoke/<int:device_id>", methods=["POST"])
@login_required
def revoke(device_id):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_db() as conn:
        conn.execute("UPDATE devices SET status='revoked', revoked_at=? WHERE id=?", (now, device_id))
        conn.commit()
    return redirect(url_for("index"))


@app.route("/reactivate/<int:device_id>", methods=["POST"])
@login_required
def reactivate(device_id):
    with get_db() as conn:
        conn.execute("UPDATE devices SET status='active', revoked_at=NULL WHERE id=?", (device_id,))
        conn.commit()
    return redirect(url_for("index"))


@app.route("/delete/<int:device_id>", methods=["POST"])
@login_required
def delete(device_id):
    with get_db() as conn:
        conn.execute("DELETE FROM devices WHERE id=?", (device_id,))
        conn.commit()
    return redirect(url_for("index"))


# ── App REST API ──────────────────────────────────────────────────────────────

@app.route("/api/status")
def api_status():
    # Validate API key when one is configured (skipped in local dev)
    if API_KEY and request.headers.get("X-API-Key") != API_KEY:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    code = request.args.get("code", "").strip().upper()
    if not code:
        return jsonify({"status": "error", "message": "Missing device code"}), 400

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM devices WHERE device_code=?", (code,)
        ).fetchone()
        if row:
            conn.execute("UPDATE devices SET last_seen=? WHERE device_code=?", (now, code))
            conn.commit()
            return jsonify({"status": row["status"], "name": row["device_name"]})
        else:
            return jsonify({"status": "unknown"})


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "0.0.0.0")
    print(f"\n  Barcode Scanner License Server")
    print(f"  Admin UI : http://localhost:{port}")
    print(f"  Password : {ADMIN_PASSWORD}")
    if not API_KEY:
        print(f"  API Key  : (none — set API_KEY env var for production)")
    print(f"  Press Ctrl+C to stop\n")
    app.run(host=host, port=port, debug=False)
