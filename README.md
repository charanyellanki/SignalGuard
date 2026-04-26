# SignalGuard — Real-time Anomaly Detection for Nokē Smart Entry Units

Streaming anomaly detection for a simulated deployment of smart-lock units across self-storage facilities. Telemetry is ingested by a unified **FastAPI** service into Postgres, scored in-process with **Isolation Forest** (scikit-learn) and an **LSTM autoencoder** (PyTorch), and anomalies fan out to a React operations dashboard over WebSockets. Optional **Weights & Biases** artifacts and a **retrain** GitHub Action support MLOps-style workflows.

This is a portfolio project demonstrating end-to-end production ML engineering patterns — not a research result. Results from validating the approach against the public [SKAB](https://github.com/waico/SKAB) benchmark can be reported in `make validate-skab` / the notebook in `notebooks/`.

---

## Architecture

```
┌──────────────────────────────────────────────────┐
│              FastAPI (unified service)            │
│  REST + ingest  │  embedded simulator  │  ML      │
│  + Alembic        │  (optional)          │  IF+LSTM │
│  + LISTEN/NOTIFY  │                      │  poller  │
└───────────────────────┬────────────────────────────┘
                        ▼
                   ┌──────────┐
                   │ Postgres │
                   └────┬─────┘
                        │ WebSocket
                        ▼
                 ┌─────────────┐
                 │  React app  │
                 └─────────────┘
```

## Tech stack

| Layer         | Choice |
|--------------|--------|
| Ingest / queue | Postgres + `processed` flag (no Kafka) |
| ML            | scikit-learn (IsolationForest) + PyTorch (LSTM AE), optional W&B |
| Storage       | PostgreSQL, SQLAlchemy 2.x async, Alembic |
| API           | FastAPI, WebSocket via Postgres `LISTEN/NOTIFY` |
| Frontend      | Vite + React + TypeScript + Tailwind + shadcn/ui + TanStack Query |
| CI/CD         | GitHub Actions (GHCR, Render deploy hook, `retrain.yml`) |

## How to run

```bash
cp .env.example .env
make up
```

- **Dashboard** — http://localhost:5173  
- **API docs** — http://localhost:8000/docs  

`make down` stops containers (keeps data); `make clean` drops volumes. See `make help`.

## Key design decisions

**Why no Kafka.** Telemetry is written to Postgres and claimed with `SELECT … FOR UPDATE SKIP LOCKED` for simple horizontal scaling without a broker.

**Why a single API service.** The detector runs as a background task in the same process as the API (and an optional in-process simulator), which fits a single free Render web service. Legacy split services are under `backend/archive/` for reference.

**MLOps.** `backend/api/train.py` logs to W&B; `.github/workflows/retrain.yml` can train on data from Supabase, push a `signalguard-models:production` artifact, and trigger a Render redeploy. Configure `WANDB_*` and database secrets in GitHub.

**Why SQLAlchemy async + Alembic.** Autogenerate against models keeps the schema in code; `backend/api/alembic/` holds migrations.

## Project layout

```
SignalGuard/
├── backend/
│   ├── api/                 # FastAPI: routes, ML detectors, train.py, simulation, Alembic
│   └── archive/             # old split services (reference only; not used by default compose)
├── frontend/                # Vite + React dashboard
├── notebooks/               # e.g. SKAB validation
├── deploy/                  # production-oriented compose
├── .github/workflows/      # deploy.yml, retrain.yml
├── docker-compose.yml
└── Makefile
```

## License

MIT.
