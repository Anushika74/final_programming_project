#!/usr/bin/env bash
#
# Install SystemIQ as a systemd service so it collects metrics continuously and
# starts automatically on boot.
#
# Usage (run with sudo from the repo root):
#     sudo bash deploy/install_service.sh
#
# It auto-detects your username and absolute paths, generates
# /etc/systemd/system/systemiq.service, and enables + starts it.
#
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Please run with sudo:  sudo bash deploy/install_service.sh"
  exit 1
fi

# The user that should own the service (the human who ran sudo, not root).
RUN_USER="${SUDO_USER:-root}"
if [[ "$RUN_USER" == "root" ]]; then
  echo "WARNING: could not detect a non-root user; the service will run as root."
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND="$REPO_DIR/backend"
VENV_BIN="$BACKEND/.venv/bin"

if [[ ! -x "$VENV_BIN/uvicorn" ]]; then
  echo "ERROR: virtualenv not found at $VENV_BIN"
  echo "Create it first:"
  echo "  cd $BACKEND && uv venv --python 3.12 && source .venv/bin/activate && uv pip install -r requirements.txt"
  exit 1
fi
if [[ ! -f "$BACKEND/.env" ]]; then
  echo "Note: $BACKEND/.env not found; copying from .env.example"
  cp "$BACKEND/.env.example" "$BACKEND/.env"
  chown "$RUN_USER":"$RUN_USER" "$BACKEND/.env" 2>/dev/null || true
fi

SERVICE_PATH="/etc/systemd/system/systemiq.service"
echo "Writing $SERVICE_PATH (user=$RUN_USER, backend=$BACKEND)"

cat > "$SERVICE_PATH" <<EOF
[Unit]
Description=SystemIQ backend (AI system monitoring + metrics collection)
After=network.target

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$BACKEND
Environment=PATH=$VENV_BIN:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ExecStartPre=$VENV_BIN/alembic upgrade head
ExecStart=$VENV_BIN/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now systemiq

echo
echo "Installed and started. Useful commands:"
echo "  systemctl status systemiq        # check it is running"
echo "  journalctl -u systemiq -f        # follow live logs"
echo "  sudo systemctl restart systemiq  # restart"
echo "  sudo systemctl stop systemiq     # stop"
echo "  sudo systemctl disable --now systemiq   # stop + remove from boot"
echo
systemctl --no-pager --full status systemiq || true
