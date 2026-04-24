# Sentinel — Real-time Anomaly Detection for IoT Device Fleets

Streaming anomaly detection for a simulated fleet of 500 smart-lock IoT devices. Telemetry flows through Kafka into an async detection service that runs **Isolation Forest** (sklearn) and an **LSTM autoencoder** (PyTorch) side-by-side; anomalies land in Postgres and fan out to a React operations dashboard over WebSockets.

This is a portfolio project demonstrating end-to-end production ML engineering patterns — not a research result. Results from validating the approach against the public [SKAB](https://github.com/waico/SKAB) benchmark are reported below.

---

## Architecture

![architecture](docs/architecture.png)

```
┌──────────────────┐    ┌─────────┐    ┌────────────────────┐    ┌──────────┐
│ device-simulator │───▶│  Kafka  │───▶│ detection-service  │───▶│ Postgres │
│   (500 devices)  │    │ (KRaft) │    │  IForest + LSTM-AE │    │          │
└──────────────────┘    └─────────┘    └────────────────────┘    └────┬─────┘
                                                                      │
                                                         LISTEN/NOTIFY│
                                                                      ▼
                                          ┌─────────────┐    ┌────────────────┐
                                          │   React     │◀──▶│    FastAPI     │
                                          │  dashboard  │ WS │  (REST + WS)   │
                                          └─────────────┘    └────────────────┘
```

## Tech stack

| Layer        | Choice                                                              |
|--------------|---------------------------------------------------------------------|
| Streaming    | Kafka (KRaft mode, single broker) + `aiokafka`                      |
| ML           | scikit-learn 1.5 (IsolationForest) + PyTorch 2.x (LSTM autoencoder) |
| Storage      | PostgreSQL 16, SQLAlchemy 2.x async, asyncpg, Alembic migrations    |
| API          | FastAPI + Pydantic v2 + uvicorn, WebSocket via Postgres LISTEN/NOTIFY |
| Frontend     | Vite + React 18 + TypeScript + Tailwind + shadcn/ui + recharts + TanStack Query |
| Orchestration| Docker Compose v2                                                   |

Python 3.11+, strict TypeScript on the frontend, fully local (no cloud dependencies).

## How to run

```bash
cp .env.example .env
make up
```

Then open:
- **Dashboard** — http://localhost:5173
- **API docs** — http://localhost:8000/docs

Within ~30 seconds the device grid populates and anomalies start appearing in the live feed. `make down` to stop (keeps data), `make clean` to wipe postgres + trained models.

See `make help` for the full command list.

## Key design decisions

**Why Kafka.** At 500 devices × 1 msg/5s ≈ 100 msg/s, Kafka is overkill *for throughput alone* — a socket would handle it. It's here because the project is a demo of streaming patterns the detection service can exploit: consumer-group scale-out, replay from offsets when a model is retrained, and durable decoupling so a detector crash doesn't drop telemetry. All three properties are awkward to retrofit; cheap to get from Kafka on day one.

**Why Isolation Forest *and* an LSTM autoencoder.** IForest is fast, interpretable, and catches point anomalies per-sample (sudden battery cliff, RSSI floor). It has no memory of the sequence. An LSTM autoencoder catches patterns IForest structurally cannot — a device whose readings are individually fine but whose *sequence* is off (access pattern drift, slow signal degradation). Running both in parallel lets the dashboard show which model flagged what, which is the interesting ML-engineering story for the portfolio.

**Why Postgres LISTEN/NOTIFY for the WebSocket fanout.** Adding Redis for a single pub-sub channel wasn't worth the operational surface area. LISTEN/NOTIFY piggy-backs on a connection we already have. The notify payload only carries the anomaly id; the WS handler re-reads the row, which stays well under Postgres' 8 kB payload cap and means the client gets a consistent view even if the notification races the write.

**Why SQLAlchemy async + Alembic.** Async all the way through means the detection service and API share one database driver pattern. Alembic for migrations because autogenerate against SQLAlchemy models is the lowest-friction way to keep schema in code.

**Why TanStack Query instead of Redux.** Anomaly and device data are fundamentally server state with caching, invalidation, and refetching concerns — exactly what TanStack Query handles. Redux would be a second source of truth for the same data.

**Why train-on-startup, not train-in-Dockerfile.** Baking models into images ties training time to image builds and bloats every rebuild. Instead the detection service trains synthetic baseline models on first boot if the `detection_models` volume is empty, writes them there, and loads them on subsequent starts. `make train` forces a retrain.

## Project layout

```
iot-anomaly-detection/
├── docker-compose.yml          # single-command orchestration
├── Makefile                    # make up | down | logs | train | clean
├── .env.example
├── device-simulator/           # Kafka producer, 500 virtual devices
├── detection-service/          # aiokafka consumer, IForest + LSTM-AE
│   ├── models/                 # model implementations
│   ├── models/trained/         # serialized models (volume-mounted)
│   └── train.py                # synthetic-data training entrypoint
├── api/                        # FastAPI: REST + WS + Alembic migrations
├── frontend/                   # Vite + React + shadcn/ui dashboard
├── notebooks/                  # SKAB validation
└── docs/
```

## Results

*To be filled after running `make validate-skab` on the SKAB dataset. Expected reporting: per-model precision / recall / F1, detection latency distribution, false-positive rate per device-hour.*

## License

MIT.
