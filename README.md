# SystemIQ

**An AI-powered system monitoring and optimization platform**

SystemIQ is a system monitoring dashboard I built for my final-year HND project. It tracks live OS metrics, stores them for trend analysis, generates recommendations, forecasts future resource usage using machine learning, and lets you ask it plain-language questions about what's happening on your machine. It can also run a set of optimization tasks — safely, and only after you confirm — all from a real-time web dashboard.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [API Overview](#api-overview)
- [Machine Learning Workflow](#machine-learning-workflow)
- [Testing](#testing)
- [Deployment](#deployment)

---

## Features

| # | Feature |
|---|---------|
| 1 | Real-time system monitoring (CPU, memory, disk, network, load) |
| 2 | Process monitoring — search, sort, inspect, and terminate processes |
| 3 | Live updates over WebSocket |
| 4 | Historical charts and time-range analytics |
| 5 | AI-generated recommendations |
| 6 | File analyzer (duplicates, large/temp files, empty folders) |
| 7 | Log analyzer that explains errors in plain language |
| 8 | Predictive analytics using scikit-learn forecasting |
| 9 | A natural-language assistant you can ask questions |
| 10 | Optimization actions, gated behind a confirmation step |
| 11 | Email and desktop alerts |
| 12 | JWT authentication with role-based access control (user CRUD) |
| 13 | Hardware health and thermal intelligence — sensors, throttling, thermal forecasts |

## Architecture

I built SystemIQ around a clean three-layer architecture, keeping the HTTP/WebSocket layer, the business logic, and the data layer clearly separated:

![SystemIQ architecture diagram](docs/architecture(1).svg)

## Tech Stack

- **Backend:** Python 3.12, FastAPI, WebSockets, psutil, SQLAlchemy 2.x, Alembic
- **Frontend:** React 18, Vite, Tailwind CSS, Recharts, Axios
- **Machine Learning:** scikit-learn, pandas, NumPy
- **Database:** MySQL (via the PyMySQL driver)
- **Authentication:** JWT (python-jose), passlib[bcrypt]

> The app is database-agnostic thanks to SQLAlchemy. It defaults to **MySQL**, but also runs on SQLite or PostgreSQL by just changing the `DATABASE_URL` value — no code changes needed.

## Project Structure

```
systemIQ/
├── backend/
│   ├── app/
│   │   ├── api/            # REST routers + WebSocket endpoint
│   │   ├── core/           # config, database, security, logging
│   │   ├── models/         # SQLAlchemy ORM models
│   │   ├── schemas/        # Pydantic request/response models
│   │   ├── services/       # business logic (one module per domain)
│   │   ├── hardware/       # sensor readers (psutil + /sys)
│   │   ├── ml/             # ML training and forecasting
│   │   └── main.py         # FastAPI application entry point
│   ├── alembic/            # database migrations
│   ├── tests/              # pytest suite
│   └── requirements.txt
├── frontend/               # React + Vite + Tailwind app
├── deploy/                 # systemd service + install script
├── docs/                   # documentation
└── docker-compose.yml
```

## Getting Started

### Prerequisites
- Python 3.12
- Node.js 18+
- MySQL 8

### 1. Create the database
```bash
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS systemiq;"
```

### 2. Backend
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then set DATABASE_URL and SECRET_KEY
alembic upgrade head          # create the tables
uvicorn app.main:app --reload # http://localhost:8000  (API docs at /docs)
```

A default admin account is created the first time you run it (configurable in `.env`):
`admin / admin123` — change this before using it for anything real.

### 3. Frontend
```bash
cd frontend
npm install
cp .env.example .env
npm run dev                   # http://localhost:5173
```

## Configuration

All backend settings live in `backend/.env`. The one you'll care about most is the database URL:

```dotenv
# MySQL (default)
DATABASE_URL=mysql+pymysql://root:yourpassword@localhost:3306/systemiq

# SQLite (alternative, no setup)
# DATABASE_URL=sqlite:///./systemiq.db

# PostgreSQL (alternative)
# DATABASE_URL=postgresql+psycopg://systemiq:password@localhost:5432/systemiq

SECRET_KEY=change_me_to_a_long_random_string
```

## API Overview

Interactive API docs are available at `http://localhost:8000/docs` once the backend is running. The full endpoint list is documented in [`docs/API.md`](docs/API.md).

## Machine Learning Workflow

The app continuously collects and stores historical metrics. From that data, the forecaster builds lag features — using the last few readings to predict the next — and trains a Random Forest model for short-term CPU/memory prediction alongside a Linear Regression model for disk-growth trends. It forecasts the next several minutes and flags an overload risk where relevant. Models retrain automatically every 24 hours. More detail is in [`docs/ML.md`](docs/ML.md).

## Testing

```bash
cd backend
source .venv/bin/activate
pytest -q
```

## Deployment

The backend can run continuously as a `systemd` service (see `deploy/`) or in containers via `docker-compose`. See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) for the full walkthrough.

---

*A final-year individual software project.*
