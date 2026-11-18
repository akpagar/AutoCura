# AutoCura — Architecture

This document describes the system **as implemented**, not as originally
proposed. Where the build diverged from an earlier proposal or spec, that
divergence is called out explicitly rather than glossed over — an honest
architecture doc is more defensible in review than one that quietly
matches whatever was promised.

## 1. Core idea

AutoCura closes the loop that most monitoring tools leave open. Tools like
Prometheus or Nagios detect a problem and alert a human. AutoCura detects,
predicts, decides, acts, and — critically — **verifies that the action
actually worked** before calling it resolved. If it didn't, AutoCura
retries within a bounded limit, then escalates instead of looping forever.

```
OBSERVE -> ANALYZE -> PREDICT -> DECIDE -> ACT -> VERIFY -> LEARN
```

"Learn" here means *recorded for later analysis* (every prediction,
decision, and recovery attempt is persisted) -- not that the decision
engine currently retrains itself from that history. See section 7 for
the honest version of that boundary.

## 2. What AutoCura monitors

This is the most important scoping decision in the whole project, so it's
stated plainly: AutoCura monitors **its own host machine's resources**
(via `psutil`) and a small set of **controlled Docker test containers** it
owns directly -- not a fleet of live production services with real user
traffic.

This was a deliberate constraint, not an oversight. The system must be
safe to run on a student's own laptop: no destructive operations on the
real OS, no arbitrary shell execution, no touching anything outside its
own sandbox. Every recovery action refuses to act on any container whose
name doesn't start with `autocura_test_`. The trade-off is that "cloud
applications and services" in the usual sense (a fleet of web apps behind
a load balancer) isn't literally present -- it's represented by four
containers: `autocura_test_primary_service` and a fixed pool of three
workers (`worker_1/2/3`), described further in section 6.

## 3. End-to-end pipeline

```
Controlled test environment (Docker containers)
        |
        v
Monitoring module  (psutil: CPU, memory, disk, network; Docker container state for the primary test service)
        |
        v
Preprocessing + feature engineering  (clean -> encode -> engineer)
        |
   +----+----+
   |         |
   v         v
Anomaly    ML failure-type
detection  classifier
(thresholds +   (Random Forest,
 Isolation       trained against
 Forest)         Logistic Regression
                 and Gradient Boosting)
   |         |
   +----+----+
        |
        v
Decision engine  (severity scoring + rule-based action selection)
        |
        v
Recovery module  (Docker SDK: restart / scale / redistribute / cleanup)
        |
        v
Recovery verifier  (before/after metric comparison, retry, escalate)
        |
        v
Database  (every metric, prediction, decision, recovery attempt, alert)
        |
        v
React dashboard  (live status, history, manual controls)
```

The background scheduler (`app/utils/scheduler.py::PeriodicTask`) runs
this whole chain automatically after every monitoring cycle
(`MONITORING_INTERVAL_SECONDS`, default 10s) via
`app/services/pipeline_service.py`, gated by a cooldown
(`AUTO_RECOVERY_COOLDOWN_SECONDS`, default 30s) so a persistent condition
doesn't trigger a new recovery attempt on every single tick. Every stage
is also independently callable via its own API endpoint for manual/demo
use.

## 4. Module boundaries

Strict separation was kept between concerns, on purpose:

| Module | Responsibility | Never does |
|---|---|---|
| `app/monitoring/` | Read raw system/container state | Make decisions, write to DB directly (that's `monitoring_service.py`) |
| `app/ml/` | Train, load, and run the classifier + anomaly detector | Talk to the database, call Docker |
| `app/decision/` | Turn a prediction into a recommended action | Execute anything, talk to Docker |
| `app/recovery/` | Execute one action against Docker | Decide *which* action to take |
| `app/services/` | Orchestrate the above, persist results | Contain business logic itself (delegates to the modules above) |
| `app/api/` | HTTP routing, request/response shape | Business logic |

This is why, for example, `recovery_rules.py` is pure data plus a lookup
function with no I/O at all -- it's independently unit-testable without a
database, a model, or Docker.

## 5. Failure simulation — how it stays safe

Five simulated failure scenarios exist (`/api/simulation/*`) so the full
loop can be demonstrated without waiting for a real fault. They are **not
all implemented the same way**, and the difference matters for anyone
evaluating whether this is "real":

- **CPU, memory, disk, network** overrides are injected at the *metrics
  reporting* layer (`app/recovery/simulation_state.py`). They do not
  stress the real host's CPU or RAM. This was a deliberate choice --
  portably and safely spiking real resources on a student's own Windows
  machine is both risky and platform-dependent, and the project's own
  safety constraint explicitly forbids dangerous host operations.
  `MonitoringService.collect_current_metrics()` applies the override
  before returning a sample, so every downstream consumer (API,
  scheduler, ML pipeline) sees the same simulated state consistently.
- **Disk** additionally creates **real files** in a project-local scratch
  directory (`.autocura_scratch/`), so the cleanup action has something
  genuine to delete -- this part isn't simulated.
- **Service failure** stops the actual `autocura_test_primary_service`
  container (when Docker is reachable), and the monitoring layer reads
  that container's real state through the Docker SDK. Without Docker (or
  without the container) it is a simulated flag, and the health signal
  reports "running" (the backend itself is up), so a service failure
  can only be simulated.

When a recovery action completes successfully against a simulated
scenario, it also calls `simulation_state.resolve_scenario()` to clear
the relevant override -- representing "the corrective action resolved
the condition." Without this, verification would always fail against a
simulated failure, since nothing would ever bring the reported metric
back down on its own. This was a real bug caught during development (see
`recovery_strategy.md` section 4) and fixed before it shipped.

## 6. The controlled test environment

Four containers, defined in `infrastructure/docker-compose.yml`, all
built from the same minimal image (`infrastructure/services/test_service/`
-- a dependency-free Python stdlib HTTP server):

- `autocura_test_primary_service` -- the restart target
- `autocura_test_worker_1/2/3` -- a fixed pool used for scale/redistribute

Plain Docker containers have no native "scale" verb (that's a
Kubernetes/Swarm concept) -- so "scaling" means starting/stopping members
of this fixed pool to reach a target replica count, and "redistribution"
means stopping one worker and confirming another is running to absorb
its load. This is a simplified stand-in for real elastic scaling,
appropriate to a controlled student-project test environment, not a
claim of production-grade orchestration.

The backend container is given access to the host's Docker socket
(`/var/run/docker.sock`) so its Docker SDK calls can control these
sibling containers -- the standard "Docker-out-of-Docker" pattern, which
works with Docker Desktop on Windows without extra configuration.

**Graceful degradation:** every function in `app/recovery/` checks
whether the Docker daemon is reachable first
(`app/recovery/docker_client.py::get_docker_client()`). If it isn't --
Docker Desktop not running, or the backend running outside Docker with no
socket mounted -- every recovery action returns a clearly-labeled
`"simulated": true` result instead of crashing. The whole system stays
demonstrable without a live Docker daemon.

## 7. Honest boundaries

Things worth naming plainly, since a reviewer will ask about them anyway:

- **No persisted knowledge base.** The decision engine's rules
  (`recovery_rules.py`) are a hardcoded Python table, not data read from
  the database. Past decisions and recoveries are stored as an audit
  trail, but the decision engine does not currently query that history
  to influence future choices -- it is stateless per decision.
- **`latency` and `error_rate` are baseline values**, not measured from a
  real request pipeline, since no load-generating client exists in the
  project yet. Every other monitored metric (CPU, memory, disk, network,
  service status) is a genuine live reading.
- **The 99%+ classifier accuracy is on a synthetic dataset** generated
  with realistic but intentionally separable class distributions (see
  `docs/testing.md`). It demonstrates that the training pipeline works
  correctly, not that the model has been validated against real-world
  failure data.
- **Single relational database for everything**, including logs -- no
  separate document store. This is simpler to operate and sufficient at
  this project's scale.
- **Inference-time preprocessing skips row-validation.** Training
  preprocessing (`preprocess.py::clean_dataset`) drops out-of-range rows;
  live prediction (`predict.py`) reuses the same encoding and feature
  engineering but does not re-validate bounds on the single live sample,
  since there's nothing to "drop" from one reading. An out-of-range live
  value would reach the model unfiltered.

## 8. Technology stack

| Layer | Choice |
|---|---|
| Backend | Python 3.11+, FastAPI, Uvicorn, Pydantic, SQLAlchemy |
| ML | scikit-learn, pandas, numpy, joblib |
| Monitoring | psutil, Docker SDK |
| Database | PostgreSQL (production) / SQLite (dev, tests) |
| Frontend | React 18, Vite, Axios, Recharts, React Router |
| Auth | JWT (python-jose), bcrypt (passlib) |
| Infra | Docker, Docker Compose, nginx |
| Testing | pytest, FastAPI TestClient |

See `README.md` for setup instructions and `docs/api_contracts.md` for
the exact JSON shape each stage of the pipeline hands to the next.
