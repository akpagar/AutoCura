# AutoCura — Testing

## 1. Running the suite

```powershell
cd backend
.venv\Scripts\Activate.ps1
python -m pytest -v
```

**41 tests across 6 files.** No live PostgreSQL connection, no Docker
daemon, and no pre-trained model in `trained_models/` are required --
`conftest.py` sets all of that up and tears it down automatically (see
section 3).

## 2. What each file covers

| File | Tests | What it exercises |
|---|---|---|
| `test_api.py` | 4 | Health check, register/login flow, wrong-password rejection |
| `test_monitoring.py` | 7 | Live metric collection, history, start/stop the collector, threshold-triggered alerts, alert acknowledgement, each raw collector's output shape |
| `test_prediction.py` | 6 | Dataset cleaning (drops out-of-range rows), categorical encoding (known + unknown service status), the `/predict` endpoint's shape, a concrete CPU-overload scenario classified correctly, prediction history |
| `test_decision.py` | 9 | Every entry in the failure-type -> action rule table, the CRITICAL-severity disk-exhaustion regression (section 3 below), severity escalation from multiple threshold breaches, the `/evaluate` endpoint and its history |
| `test_recovery.py` | 11 | The `autocura_test_` prefix safety guard, graceful degradation when Docker is unreachable, real file creation/cleanup in the disk-cleanup action, simulation state apply/clear/resolve, the simulation and recovery-execute API endpoints |
| `test_dashboard.py` | 4 | Summary/metrics/failures/recoveries/alerts endpoints, and **one true end-to-end test**: inject a CPU-overload simulation -> confirm the decision engine recommends `scale_service` -> execute recovery -> confirm it actually succeeds -> reset |

## 3. The regression test worth highlighting

`test_decision.py::test_disk_exhaustion_stays_on_cleanup_even_at_critical`
exists because an earlier version of the decision engine had a real bug:
CRITICAL severity force-escalated *every* failure type to
`restart_service`, including disk exhaustion -- where restarting does
nothing to free disk space. This test pins the correct behavior so that
mistake can't silently come back:

```python
def test_disk_exhaustion_stays_on_cleanup_even_at_critical():
    action, _ = resolve_action("disk_exhaustion", "CRITICAL")
    assert action == "cleanup_disk"
```

Full writeup of the bug and the fix: `recovery_strategy.md` section 3.

## 4. Tests that run without any fixtures at all

A deliberate design choice: `app/decision/` has zero I/O (no database, no
model, no Docker), so its logic is tested as plain function calls with no
setup:

```python
def test_cpu_overload_maps_to_scale_service():
    action, _ = resolve_action("cpu_overload", "HIGH")
    assert action == "scale_service"
```

Same pattern for `app/recovery/simulation_state.py` and
`app/recovery/docker_client.py::is_controlled_container()` -- pure logic,
fast, deterministic, no mocking required.

## 5. What `conftest.py` actually does

Every test that needs the full app (marked by taking a `client` fixture
parameter) gets:

1. **A throwaway SQLite database** (`DATABASE_URL` overridden to
   `sqlite:///./test_autocura.db`), disposed and deleted after the
   session -- Windows keeps SQLite files locked while any pooled
   connection is open, so `engine.dispose()` runs before the delete.
2. **A real, freshly trained model** in a temp `MODEL_DIR` -- the fixture
   calls the exact same `generate_dataset()` and `train_and_select_best()`
   functions the real project uses, just on a smaller (1,000-row) dataset
   for test speed. This means `/api/prediction/predict` and
   `/api/decision/evaluate` are tested against a genuine trained model,
   not a mock.
3. **A disabled background scheduler**
   (`MONITORING_INTERVAL_SECONDS=3600`) so the real 10-second collection
   loop doesn't fire mid-test-run and interfere with assertions.
4. **Shortened recovery timing**
   (`RECOVERY_STABILIZATION_WAIT_SECONDS=1`, `RECOVERY_RETRY_LIMIT=2`)
   so recovery tests don't take the full 15s production timeout.

## 6. Honest gaps

- No frontend test suite exists (no Jest/Vitest/React Testing Library).
  The frontend was verified with TypeScript-compiler parse checks and a
  custom import-resolution script during development, not automated unit
  tests shipped in the repo.
- No load/performance testing -- nothing measures behavior under
  concurrent requests or sustained high-frequency monitoring.
- No test exercises a real Docker daemon; `test_recovery.py` tests the
  Docker-unavailable fallback path specifically, since that's the
  reliably reproducible state in CI and on a machine without Docker
  Desktop running. The real-Docker path (`"simulated": false`) is
  exercised manually, not by the automated suite.
