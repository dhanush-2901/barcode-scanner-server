#!/bin/bash
# Run this script ON your GCE VM (not on your PC)
# Usage: bash deploy_gce.sh
set -e

APP_DIR="/opt/barcode-scanner"
VENV="$APP_DIR/venv"
SERVICE="barcode-scanner"
RUN_AS=$(whoami)

echo "=== Barcode Scanner License Server — GCE Setup ==="
echo "Installing as user: $RUN_AS"
echo

# ── Install system packages ───────────────────────────────────────────────────
sudo apt-get update -qq
sudo apt-get install -y python3 python3-pip python3-venv

# ── Create app directory ──────────────────────────────────────────────────────
sudo mkdir -p "$APP_DIR/data"
sudo chown -R "$RUN_AS:$RUN_AS" "$APP_DIR"

# Copy server files (run this script from inside the server/ folder)
cp -r . "$APP_DIR/"

# ── Python virtual environment ────────────────────────────────────────────────
python3 -m venv "$VENV"
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"

# ── Create .env if it doesn't exist yet ──────────────────────────────────────
if [ ! -f "$APP_DIR/.env" ]; then
  GENERATED_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
  GENERATED_API_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(20))")

  cat > "$APP_DIR/.env" << EOF
# Admin web UI password — CHANGE THIS
ADMIN_PASSWORD=admin123

# Random secrets — already generated for you
SECRET_KEY=$GENERATED_SECRET
API_KEY=$GENERATED_API_KEY

# SQLite database path (inside the persistent data folder)
DATABASE_PATH=$APP_DIR/data/devices.db

# Internal port — nginx proxies this, so no extra GCP firewall rule is needed
PORT=8765
EOF
  echo "Created $APP_DIR/.env"
fi

# ── Systemd service ───────────────────────────────────────────────────────────
sudo tee /etc/systemd/system/$SERVICE.service > /dev/null << EOF
[Unit]
Description=Barcode Scanner License Server
After=network.target

[Service]
Type=simple
User=$RUN_AS
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$VENV/bin/gunicorn app:app --bind 0.0.0.0:5000 --workers 2 --timeout 30
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable  $SERVICE
sudo systemctl restart $SERVICE

# ── Print summary ─────────────────────────────────────────────────────────────
echo
echo "=== Setup complete ==="
sudo systemctl status $SERVICE --no-pager -l
echo
echo "──────────────────────────────────────────────────"
EXTERNAL_IP=$(curl -sf "http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/externalIp" -H "Metadata-Flavor: Google" || echo "<unknown>")
API_KEY_VAL=$(grep "^API_KEY=" "$APP_DIR/.env" | cut -d= -f2)
ADMIN_PW=$(grep "^ADMIN_PASSWORD=" "$APP_DIR/.env" | cut -d= -f2)
echo "  External IP    : $EXTERNAL_IP"
echo "  Admin UI       : http://$EXTERNAL_IP:5000"
echo "  Admin password : $ADMIN_PW"
echo "  API Key        : $API_KEY_VAL"
echo "──────────────────────────────────────────────────"
echo
echo "Next steps:"
echo "  1. IMPORTANT: Edit $APP_DIR/.env  →  change ADMIN_PASSWORD"
echo "     Then run: sudo systemctl restart $SERVICE"
echo
echo "  2. Add the nginx snippet to your existing nginx site config:"
echo "     See: nginx.conf in the server folder"
echo "     Then run: sudo nginx -t && sudo systemctl reload nginx"
echo "     (No new GCP firewall rule needed — nginx is already on 80/443)"
echo
echo "  3. In app/build.gradle set:"
echo "     LICENSE_SERVER_URL = \"https://your-domain.com/barcode-scanner\""
echo "     LICENSE_API_KEY    = \"$API_KEY_VAL\""
echo "  Then rebuild the APK."
echo "──────────────────────────────────────────────────"
