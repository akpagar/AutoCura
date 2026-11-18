# AutoCura — An Autonomous Recovery Engine for Cloud Infrastructure

> OBSERVE → ANALYZE → PREDICT → DECIDE → ACT → VERIFY → LEARN

AutoCura is a final-year B.Tech (AI & Data Science) project that demonstrates
autonomous cloud infrastructure self-healing: continuous monitoring, ML-based
failure prediction, rule-based decision making, automated recovery in a
controlled Docker test environment, and recovery verification with feedback.

This README is built up phase by phase alongside the implementation.
**Status: Phase 8 complete — the project is done.** All eight phases
built, tested, and documented. See `docs/` for architecture, API
contracts, recovery strategy, and testing details.

---

## 1. Project Overview

Modern cloud applications require high availability. AutoCura continuously
observes system metrics (CPU, memory, disk, network, service health),
predicts and detects failures, decides on an appropriate recovery action,
executes that action against a **safe, controlled test environment**, and
verifies whether the recovery actually worked — storing every step for
historical analysis and a dashboard.

## 2. Problem Statement

Failures such as service crashes, CPU overload, memory exhaustion, disk
exhaustion, and network degradation cause downtime. Most systems only
*alert* humans; AutoCura closes the loop by *acting* automatically, within
safe, pre-approved boundaries.

## 3. Objectives

See `docs/architecture.md` for the full workflow. In short: monitor, detect,
predict, decide, act, verify, and learn — continuously.

## 4. Architecture

```
Test Services → Monitoring → Preprocessing → Failure Detection + ML Prediction
    → Decision Engine → Recovery Engine → Recovery Verification
    → Feedback + Database → React Dashboard
```

Full diagram and rationale: `docs/architecture.md`.

## 5. Technology Stack

| Layer          | Technology                                   |
|----------------|-----------------------------------------------|
| Backend        | Python 3.11, FastAPI, Uvicorn, Pydantic       |
| Database       | PostgreSQL, SQLAlchemy                        |
| ML             | pandas, numpy, scikit-learn, joblib           |
| Monitoring     | psutil, Docker SDK                            |
| Infrastructure | Docker, Docker Compose                        |
| Frontend       | React, Vite, Axios, Recharts                  |
| Auth           | JWT (python-jose), bcrypt (passlib)           |
| Testing        | pytest, FastAPI TestClient                    |

## 6. Folder Structure

```
AutoCura/
├── backend/            # FastAPI app, ML pipeline, monitoring, recovery, decision logic
├── frontend/            # React dashboard (Phase 7)
├── infrastructure/     # docker-compose fragments, test services (Phase 5)
├── scripts/             # dataset generation, training, seeding, simulation scripts
├── docs/                 # architecture, API contracts, recovery strategy, testing docs
└── docker-compose.yml   # root compose entrypoint
```

## 7. Installation (Windows + VS Code + PowerShell)

### 7.1 Prerequisites
- Python 3.11+ (`python --version`)
- PostgreSQL 16 running locally, **or** Docker Desktop (recommended — see §9)
- Node.js 18+ (for the frontend, from Phase 7 onward)
- Git

### 7.2 Backend virtual environment

From the project root, in PowerShell:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 8. Environment Variables

```powershell
copy .env.example .env
```

Then edit `backend\.env` and set at least `SECRET_KEY` and `DATABASE_URL`.
All variables are documented in `backend/.env.example` and loaded via
`app/config.py` (nothing is hard-coded elsewhere in the codebase).

## 9. Database Setup

**Option A — Docker (recommended, no local Postgres install needed):**

```powershell
cd infrastructure
docker compose up -d postgres
```

This starts PostgreSQL on `localhost:5432` with user/password/db `autocura`.

**Option B — Local PostgreSQL install:** create a database and user named
`autocura` and update `DATABASE_URL` in `.env` accordingly.

Tables are created automatically on backend startup via `init_db()` in
`app/database.py` (development convenience — a migration tool such as
Alembic would replace this in a production setting).

## 10. ML Model Training (Phase 3)

Generate the synthetic dataset and train the failure classifier + anomaly detector:

```powershell
cd backend
.venv\Scripts\Activate.ps1
cd ..
python scripts\generate_dataset.py --rows 6000
python scripts\train_model.py
```

This writes `backend/datasets/raw/monitoring_dataset.csv`, the processed
version, and the trained model artifacts to `backend/trained_models/`
(`failure_classifier.joblib`, `isolation_forest.joblib`,
`label_encoder.joblib`, `model_metadata.json`). **These files are not
committed to the repo** — model binaries are only safely portable
between machines running the exact same scikit-learn version, so each
environment trains its own. Re-run `train_model.py` any time you change
`requirements.txt`'s scikit-learn version.

`model_metadata.json` records the real accuracy/precision/recall/F1
and confusion matrix computed on a held-out test split — check it if
you want the actual numbers behind "the model works."

## 11. Starting the Backend

```powershell
cd backend
.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload
```

The API will be available at: http://localhost:8000
Interactive Swagger docs: http://localhost:8000/docs

## 12. Docker Setup (full stack: backend, Postgres, controlled test containers)

From the project root:

```powershell
docker compose up --build
```

This also builds and starts the controlled test environment the
recovery module (Phase 5) operates on: `autocura_test_primary_service`
(port 9000) and three workers, `autocura_test_worker_1/2/3` (ports
9001-9003). The backend container is given access to the host's Docker
socket so its recovery actions can restart/scale/migrate these
containers for real — see `infrastructure/docker-compose.yml` for
details. If Docker Desktop isn't running, or you run the backend
outside Docker without a docker socket mounted, every recovery action
automatically falls back to a clearly-labeled simulated result instead
of failing.

## 13. Testing

```powershell
cd backend
.venv\Scripts\Activate.ps1
python -m pytest -v
```

All tests run against a throwaway SQLite database and a throwaway
temp-directory ML model (both auto-created and cleaned up by
`tests/conftest.py`), so the full suite works without a live
PostgreSQL connection, without Docker running, and without needing
`trained_models/` populated first.

## 14. Example Workflow (Phases 1-6)

1. Start the backend (§11). The monitoring scheduler starts automatically
   (every `MONITORING_INTERVAL_SECONDS`, default 10s) and begins writing
   samples to the `metrics` table.
2. Open http://localhost:8000/docs.
3. `POST /api/auth/register` with a name/email/password.
4. `POST /api/auth/login` with the same credentials → receive a JWT.
5. `GET /api/health` → confirms the app and DB are wired up correctly.
6. `GET /api/monitoring/current` → a live CPU/memory/disk/network/service sample.
7. `GET /api/monitoring/history?limit=10` → the last 10 persisted samples.
8. `POST /api/monitoring/stop` / `POST /api/monitoring/start` → toggle the background collector.
9. Push your machine's CPU or memory past the configured threshold (see
   `.env` `CPU_THRESHOLD` / `MEMORY_THRESHOLD`) and check `GET /api/alerts`
   — a `HIGH_CPU` / `HIGH_MEMORY` alert and a matching entry in
   `GET /api/logs` should appear within one collection interval.
10. `POST /api/prediction/predict` (empty body) → a live failure prediction from the trained model.
11. `POST /api/decision/evaluate` → runs the same prediction plus the rule-based decision engine, returns the recommended recovery action.
12. **Full demo loop:** `POST /api/simulation/cpu` with `{"value": 96}` → wait a moment →
    `POST /api/decision/evaluate` (should now recommend `scale_service`) →
    `POST /api/recovery/execute` (empty body — runs the full chain, executes the action, verifies the result) →
    `POST /api/simulation/reset` to return to a healthy baseline.
13. `POST /api/simulation/disk` → creates real junk files in `backend/.autocura_scratch/` and reports high disk usage →
    `POST /api/recovery/execute` with `{"action": "cleanup_disk", "failure_type": "disk_exhaustion"}` → the junk files are actually deleted.
14. `POST /api/simulation/service-failure` (with `docker compose up` running) → actually stops the `autocura_test_primary_service` container →
    `POST /api/recovery/execute` with `{"action": "restart_service", "failure_type": "service_failure"}` → the container actually restarts.
15. `POST /api/alerts/{id}/acknowledge` → marks an alert as handled.
16. **Fully automatic demo (Phase 6 — no manual API calls needed):** with
    the backend running and `AUTO_RECOVERY_ENABLED=true` (the default),
    `POST /api/simulation/cpu` with `{"value": 96}` and then just wait.
    Within one `MONITORING_INTERVAL_SECONDS` cycle, the scheduler will
    itself detect the anomaly, predict `cpu_overload`, decide on
    `scale_service`, execute it, verify the result, and clear the
    simulated condition — all without another API call. Watch
    `GET /api/decision/history` and `GET /api/recovery/history` grow on
    their own, or just tail the backend's console log.
17. `GET /api/dashboard/summary` → the KPI values a dashboard's top cards
    would show (system health, current CPU/memory/disk, active failure
    count, recovery success rate, average recovery time).
18. `GET /api/dashboard/metrics`, `/failures`, `/recoveries`, `/alerts` →
    the time series and tables a dashboard's charts and activity feeds
    would bind to directly.

## 15. Starting the Frontend (Phase 7)

The React dashboard lives in `frontend/` and talks to the backend over
relative `/api/...` paths (Vite's dev server proxies these to
`localhost:8000`, so no host is hard-coded anywhere).

**Prerequisite:** Node.js 18+ (`node --version`). The backend must be
running first (§11).

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Register an account on the login screen,
then you land on the dashboard.

### Pages

| Page | What it does |
|---|---|
| **Login** | Register or log in; JWT is stored and attached to every later request |
| **Dashboard** | Six KPI cards (health, CPU, memory, active failures, recovery success rate, avg recovery time), CPU/memory and disk/latency charts, recent failures and recoveries |
| **Monitoring** | Live metric cards, start/stop the background collector, CPU/memory and network charts |
| **Predictions** | Run the classifier on live metrics; shows failure type, severity, probability, confidence, anomaly signals; full history table |
| **Recovery** | **The demo page** — trigger a simulated failure, run the decision engine, execute recovery, watch the history table fill in |
| **Alerts** | All alerts with severity badges and an acknowledge button |
| **Logs** | Filterable system log table |

Every page polls its endpoints on an interval (5-8s depending on page),
so data refreshes without a manual reload. Polling was chosen over
WebSockets deliberately — for this project's scope a WebSocket layer
would add real complexity without a meaningful benefit.

### Live demo flow (three clicks)

Go to **Recovery** and click, in order:
1. **CPU overload** — injects a simulated 96% CPU reading
2. **Run decision engine** — should report `cpu_overload` at HIGH/CRITICAL severity, recommending `scale_service`
3. **Execute recovery** — runs it, verifies the result, shows the recovery time

Then **Reset all simulations** to return to a healthy baseline. Or skip
step 2-3 entirely: with `AUTO_RECOVERY_ENABLED=true` (the default), just
trigger the failure and wait ~10s — the backend does the rest on its own
and the dashboard updates itself.

## 16. Further Documentation (Phase 8)

Deeper writeups live in `docs/`, each grounded in the actual code rather
than the original proposal:

| Doc | Covers |
|---|---|
| `docs/architecture.md` | Full system design, what's genuinely real vs. simulated, honest scope boundaries |
| `docs/api_contracts.md` | Exact JSON shape every pipeline stage hands to the next, copied from the real schemas |
| `docs/recovery_strategy.md` | Severity scoring, the rule table, two real bugs caught during development and how they were fixed, retry/escalation policy |
| `docs/testing.md` | What each of the 41 tests covers, the regression test for the CRITICAL-severity bug, honest gaps in coverage |

## 17. Roadmap

- [x] Phase 1 — Project structure & backend foundation
- [x] Phase 2 — Monitoring (psutil collectors + background scheduler + alerts + logs)
- [x] Phase 3 — Dataset + ML failure-prediction pipeline
- [x] Phase 4 — Decision engine
- [x] Phase 5 — Controlled Docker recovery + failure simulation
- [x] Phase 6 — End-to-end integration (automated pipeline + dashboard API)
- [x] Phase 7 — React dashboard
- [x] Phase 8 — Full testing & documentation

## 18. Troubleshooting

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: app` | Run uvicorn from inside `backend/` so `app` is importable, or ensure the venv is activated. |
| `psycopg2` install fails on Windows | Use `psycopg2-binary` (already in `requirements.txt`) rather than `psycopg2`. |
| Cannot connect to Postgres | Confirm `docker compose ps` shows `postgres` healthy, and `DATABASE_URL` matches the credentials in `infrastructure/docker-compose.yml`. |
| `ImportError: cannot import name 'StrEnum'` | Requires Python 3.11+; check `python --version`. |
| `ValueError: password cannot be longer than 72 bytes` on register/login | Known `passlib==1.7.4` + `bcrypt>=4.1` incompatibility (unrelated to your actual password). Fixed by pinning `bcrypt==4.0.1` in `requirements.txt` -- reinstall with `pip install -r requirements.txt`. |
| `RuntimeError: no running event loop` on `/api/monitoring/start` | Fixed as of this version (`start_monitoring` is now `async def`, matching `stop_monitoring`) -- pull the latest `app/api/monitoring.py`. |
| `PermissionError` deleting `test_autocura.db` after `pytest` (Windows only) | Fixed: `conftest.py` now calls `engine.dispose()` before removing the file, releasing SQLite's file lock. |
| `psycopg2.OperationalError: connection ... refused` on startup | No `.env` file yet, or Postgres isn't running. Either run `copy .env.example .env` and `docker compose up -d postgres` (see §9), or point `DATABASE_URL` at SQLite for a quick local run without Docker, e.g. `DATABASE_URL=sqlite:///./autocura.db`. |
| `ImportError: email-validator is not installed` | Fixed: `email-validator` is now pinned in `requirements.txt` (pydantic's `EmailStr` needs it but doesn't vendor it). Run `pip install -r requirements.txt` again. |
| `FileNotFoundError: No trained model found at trained_models\failure_classifier.joblib` (even after training) | Fixed: `MODEL_DIR` used to resolve relative to the current working directory, so training from the project root saved to `AutoCura/trained_models/` while the app looked in `backend/trained_models/`. It is now anchored to `backend/` via `Settings.model_dir_path` regardless of where any script is launched from. If you hit this on an older copy, move the folder into `backend/` and retrain. |
| `TypeError: can't subtract offset-naive and offset-aware datetimes` | Fixed: SQLite strips timezone info on round-trip, so comparing a stored timestamp against `utc_now()` crashed. `app/utils/helpers.py::seconds_since()` now normalises naive values to UTC before subtracting. |
| `GET / HTTP/1.1 404 Not Found` | Not a bug — no route is registered at the bare root URL. Use http://localhost:8000/docs for the Swagger UI or http://localhost:8000/api/health for a health check. |
| Pipeline logs a traceback every ~10s on first run | Expected before training. As of this version it logs one friendly line instead. Run `scripts/generate_dataset.py` then `scripts/train_model.py` to enable the automated pipeline. |
| Frontend loads but every request fails / redirects to login | The backend isn't running, or isn't on port 8000. Start it first (§11); Vite proxies `/api` to `localhost:8000` per `vite.config.js`. |
| `npm install` fails or `vite` not found | Requires Node.js 18+. Check with `node --version`, and run `npm install` from inside `frontend/`. |

### A note on which directory to run things from

Several of the errors above came down to running a command from the wrong
folder. The rule:

| Command | Run from |
|---|---|
| `python scripts\generate_dataset.py` | project root (`AutoCura/`) |
| `python scripts\train_model.py` | project root (`AutoCura/`) |
| `python -m uvicorn app.main:app --reload` | **`AutoCura/backend/`** |
| `python -m pytest` | **`AutoCura/backend/`** |
| `npm install` / `npm run dev` | **`AutoCura/frontend/`** |
| `docker compose up --build` | project root (`AutoCura/`) |

Check your PowerShell prompt before running — it shows the current folder.

## Team

| Member | Role |
|---|---|
| Amruta | Machine Learning & Decision Engine Lead |
| Prajakta Kadam | Monitoring & Data Analysis Lead |
| Anushka | System Design & Integration Lead |
| Prajkta Patil | Cloud Automation & Recovery Lead |
