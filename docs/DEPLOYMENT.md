# SystemIQ — Deployment Guide

## Option A — Local development (recommended for the demo)

I'd recommend running the backend directly on the host, since that's the only way `psutil` reports **real host metrics** instead of a container's.

```bash
# Backend
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                  # edit SECRET_KEY, thresholds, etc.
alembic upgrade head                  # or rely on auto-create on first run
uvicorn app.main:app --reload

# Frontend (separate terminal)
cd frontend
npm install
cp .env.example .env
npm run dev                           # http://localhost:5173
```

Default admin login: `admin / admin123` — change this right away.

## Option B — Docker Compose (PostgreSQL + backend + frontend)

```bash
docker compose up --build
# Frontend:  http://localhost:8080
# Backend:   http://localhost:8000/docs
```

> **Host metrics caveat:** inside a container, `psutil` only sees the container itself, not the host it's running on. If you need true host-level monitoring, either run the backend on the host directly (Option A), or uncomment `pid: "host"` / `privileged: true` for the backend service in `docker-compose.yml` (Linux only).

## Option C — systemd service (production on Ubuntu)

**Recommended path — the installer script does this for you.** From the repo root, run it and it'll detect your username and paths, generate the unit file, and enable + start the service so SystemIQ collects metrics continuously and comes back up on boot:

```bash
sudo bash deploy/install_service.sh
```

Once it's running, you can manage it with:
```bash
systemctl status systemiq               # is it running?
journalctl -u systemiq -f                # follow live logs
sudo systemctl restart systemiq          # restart
sudo systemctl disable --now systemiq    # stop + remove from boot
```

**If you'd rather set it up manually**, here's the unit file I use at `/etc/systemd/system/systemiq.service`:

```ini
[Unit]
Description=SystemIQ backend
After=network.target postgresql.service

[Service]
User=systemiq
WorkingDirectory=/opt/systemiq/backend
Environment="PATH=/opt/systemiq/backend/.venv/bin"
EnvironmentFile=/opt/systemiq/backend/.env
ExecStart=/opt/systemiq/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now systemiq
```

From there, build the frontend (`npm run build`, which outputs to `frontend/dist`) and serve it behind nginx, reverse-proxying `/api` and `/ws` to the backend.

## Database

- **Development:** SQLite by default (`DATABASE_URL=sqlite:///./systemiq.db`) — no setup needed.
- **Production:** I'd switch to PostgreSQL:
  `DATABASE_URL=postgresql+psycopg://user:pass@host:5432/systemiq`
- Apply migrations with `alembic upgrade head`. When you change a model, generate a new migration with `alembic revision --autogenerate -m "message"`.

## Production hardening checklist

Before this goes anywhere near a real deployment, I'd work through this list:

- [ ] Set a strong `SECRET_KEY` (`python -c "import secrets;print(secrets.token_urlsafe(48))"`)
- [ ] Change the default admin password
- [ ] Set `ENVIRONMENT=production` and `DEBUG=false`
- [ ] Restrict `CORS_ORIGINS` to your actual frontend origin
- [ ] Terminate TLS at nginx and use `wss://` for the WebSocket connection
- [ ] Configure SMTP for email alerts and tune the alert thresholds
- [ ] Set a sensible `METRICS_RETENTION_DAYS` so the database doesn't grow forever
- [ ] Run it behind a process manager (systemd) with auto-restart enabled
