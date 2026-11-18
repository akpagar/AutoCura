# AutoCura — Recovery Strategy

## 1. Severity calculation

The ML classifier's own severity output (in `app/ml/predict.py`) is
derived purely from its failure probability. The decision engine takes a
broader view in `app/decision/severity.py`: it starts from that ML
severity, then escalates by one level per *additional* threshold rule
breached beyond the first, and one more level if the Isolation Forest
independently flags the sample. The logic: a single borderline ML call
alone should not push severity up, but multiple corroborating signals
(several thresholds breached, or an independent anomaly model agreeing)
are a stronger signal than any one of them alone.

```
severity = ml_severity
if threshold_breaches > 1:
    severity += (threshold_breaches - 1) levels
if isolation_forest_flagged:
    severity += 1 level
severity = min(severity, CRITICAL)
```

## 2. The recovery rule table

`app/decision/recovery_rules.py` -- a plain data table, deliberately kept
free of control flow so it's easy to audit and extend without touching
engine logic:

| Failure type | Action | Rationale |
|---|---|---|
| `cpu_overload` | `scale_service` | Redistribute load across more capacity |
| `memory_exhaustion` | `restart_service` | Reclaim leaked/held memory |
| `disk_exhaustion` | `cleanup_disk` | Free space directly |
| `service_failure` | `restart_service` | Bring the service back up |
| `network_degradation` | `redistribute_workload` | Move load off the degraded path |
| `normal` | `no_action` | Nothing to do |

## 3. CRITICAL-severity escalation — and a bug caught here

The spec called for "CRITICAL -> execute strongest safe recovery
strategy." The first implementation read this as *always restart* at
CRITICAL severity, regardless of failure type. That was wrong, and the
mistake is worth documenting rather than hiding: **restarting a service
does nothing to free disk space.** A CRITICAL disk-exhaustion failure
that got escalated to `restart_service` would run an action guaranteed
not to fix the actual problem.

The fix: escalation is now per-failure-type, and only where a genuinely
*different, stronger* action helps:

| Failure type | Normal severity | CRITICAL severity |
|---|---|---|
| `cpu_overload` | `scale_service` | `scale_service` (already the strongest appropriate action) |
| `memory_exhaustion` | `restart_service` | `restart_service` (unchanged) |
| `disk_exhaustion` | `cleanup_disk` | `cleanup_disk` (unchanged -- restart would not help) |
| `service_failure` | `restart_service` | `restart_service` (unchanged) |
| `network_degradation` | `redistribute_workload` | `restart_service` (redistribution alone unlikely to be enough) |

`backend/tests/test_decision.py::test_disk_exhaustion_stays_on_cleanup_even_at_critical`
is a permanent regression test for this.

## 4. Simulation resolution — a second bug caught during Phase 6

A related issue surfaced once the automated pipeline (Phase 6) started
running recovery against *simulated* failures unattended: none of the
recovery actions had any way to affect the simulated metric override
(`app/recovery/simulation_state.py`). A simulated CPU-overload reading of
96% would stay at 96% forever, no matter what action ran, since
`scale_service` only starts/stops real containers -- it never touches
the number `collect_current_metrics()` reports.

That meant verification (section 5) would **always** report failure
against a simulated scenario, misleadingly, regardless of whether the
"right" action was chosen. The fix: `SimulationState.resolve_scenario()`
is called -- only on a successful action -- to clear the override
matching that failure type, representing "the corrective action resolved
the simulated condition." A genuinely real (non-simulated) failure has no
matching active scenario, so this is a no-op for it and doesn't affect
real-container recovery paths at all.

## 5. Recovery verification

Per the "recovery is not successful just because the action ran without
raising" principle, `app/recovery/recovery_verifier.py` does the
following after every action:

1. Wait `RECOVERY_STABILIZATION_WAIT_SECONDS` (default 5s) for the
   system to settle.
2. Collect a fresh metrics sample.
3. Compare against the metric relevant to the failure type (`cpu_usage`
   for `cpu_overload`, `memory_usage` for `memory_exhaustion`,
   `disk_usage` for `disk_exhaustion`, `latency` for
   `network_degradation`; `service_status == "running"` for
   `service_failure`).
4. Success = the relevant value dropped, or was already below its
   configured healthy threshold.
5. Record the total elapsed time as `recovery_time_seconds`.

## 6. Retry and escalation policy

`app/services/recovery_service.py::_execute_with_retries` bounds the
whole loop deliberately -- per the spec's "do not create infinite
retries":

```
for attempt in 1..RECOVERY_RETRY_LIMIT (default 3):
    execute action
    verify result
    persist a Recovery row for this attempt
    if success: mark the Failure resolved, stop
else:  # every attempt failed
    mark the Failure escalated
    raise a CRITICAL alert (source: recovery_engine)
```

Every attempt -- not just the last one -- gets its own `Recovery` row, so
the audit trail shows the full retry history, not just the final
outcome. Each retry currently blocks synchronously for up to
`RECOVERY_STABILIZATION_WAIT_SECONDS`, so a full exhausted retry sequence
can take up to `RECOVERY_RETRY_LIMIT x RECOVERY_STABILIZATION_WAIT_SECONDS`
(15s by default) before the API call returns -- a known latency
trade-off, not yet addressed by an async job/polling pattern.

## 7. Automated pipeline cooldown

The background scheduler runs the full chain after every monitoring
cycle (`MONITORING_INTERVAL_SECONDS`, default 10s). Without a limiter, a
persistent condition would trigger a brand-new recovery attempt (with
its own retry loop) on every single tick. `pipeline_service.py` checks
the timestamp of the most recent `Decision` row and skips the cycle
entirely if one was made within `AUTO_RECOVERY_COOLDOWN_SECONDS`
(default 30s) -- a deliberately simple global cooldown rather than
per-action-type throttling, traded off for predictability over
sophistication at this project's scale. This check is a single indexed
timestamp comparison, so it adds negligible overhead compared to
re-running the full anomaly + ML + decision chain on every tick
regardless.

## 8. Safety guarantees

- Every Docker action passes through
  `docker_client.py::is_controlled_container()`, which refuses any
  container name not prefixed `autocura_test_` -- no accidental (or
  malicious) action against anything outside the sandbox.
- No action ever executes an arbitrary shell command; every Docker
  interaction goes through the typed SDK (`container.restart()`,
  `.start()`, `.stop()`), never `subprocess` or `docker exec` with a
  caller-supplied string.
- Disk cleanup only ever touches a hardcoded, project-local scratch
  path (`.autocura_scratch/`) -- never a caller-supplied path, never
  anywhere on the real filesystem outside the project.
- If Docker isn't reachable, every action degrades to a clearly-labeled
  simulated result (`"simulated": true`) instead of raising, so the
  system never crashes over an unavailable optional dependency.

## Failure types and actions (8)

| Failure type | Detected by | Action |
|---|---|---|
| cpu_overload | CPU over threshold | scale_service |
| memory_exhaustion | memory over threshold | restart_service |
| disk_exhaustion | disk over threshold | cleanup_disk |
| network_degradation | latency over threshold | redistribute_workload (restart at CRITICAL) |
| service_failure | service stopped | restart_service |
| high_error_rate | error rate over threshold, everything else healthy | restart_service |
| service_degraded | service up but unhealthy | redistribute_workload |
| resource_saturation | CPU and memory over threshold together | scale_and_restart |

The Random Forest was trained on the original five failure classes. The three
newer types are identified by the threshold rules in `decision/hybrid.py`
(recorded as `rule_override` in the decision reason), not by the classifier.
Retraining the classifier on those classes would need new labelled data.

## Response delay

`RECOVERY_RESPONSE_DELAY_SECONDS` (default 8) is the pause between detecting a
failure and acting on it in the automated pipeline. During it the failure is
open, an alert is raised and dashboard health is critical. Set it to 0 for
instant recovery. The manual "Execute recovery" button has no delay.
