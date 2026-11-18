# AutoCura — API Contracts

Every JSON shape below is copied directly from the Pydantic schemas in
`backend/app/schemas/`, not re-typed from memory -- if this document and
the code ever disagree, the code is correct and this doc is stale.
Full interactive docs (with live examples) are always available at
`/docs` while the backend is running.

## 1. Monitoring -> everything downstream

`GET /api/monitoring/current` and the internal
`MonitoringService.collect_current_metrics()` both return this shape.
This is the shape every other stage (prediction, decision, recovery)
consumes as its starting point.

```json
{
  "cpu_usage": 42.3,
  "memory_usage": 61.5,
  "disk_usage": 38.0,
  "network_in": 5234123.0,
  "network_out": 3012456.0,
  "latency": 15.2,
  "error_rate": 0.0,
  "service_status": "running",
  "hostname": "localhost"
}
```

`latency` and `error_rate` are fixed baseline values, not measured from
a real request pipeline (see `architecture.md` section 7) -- every other
field is a genuine live reading from `psutil` / the Docker container state of the primary test service.

Persisted rows (`GET /api/monitoring/history`) add `id` and `timestamp`.

## 2. Monitoring -> Prediction

`POST /api/prediction/predict` accepts an optional body of overrides
(any field omitted falls back to the current live value):

```json
{
  "cpu_usage": 95.0,
  "memory_usage": null,
  "disk_usage": null,
  "network_in": null,
  "network_out": null,
  "latency": null,
  "error_rate": null,
  "service_status": null,
  "process_count": null,
  "restart_count": null
}
```

## 3. Prediction -> Decision Engine

Response of `POST /api/prediction/predict`:

```json
{
  "failure_type": "cpu_overload",
  "failure_probability": 0.94,
  "confidence": 0.87,
  "severity": "HIGH",
  "anomaly": {
    "is_anomaly": true,
    "threshold_reasons": ["cpu_usage 95.0 > 85.0"],
    "isolation_forest_flagged": false
  }
}
```

`failure_type` is one of: `normal`, `cpu_overload`, `memory_exhaustion`,
`disk_exhaustion`, `service_failure`, `network_degradation`.
`severity` is one of: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` -- note this is
the ML model's own probability-derived severity, which the decision
engine then re-scores against anomaly signals (see section 4 and
`recovery_strategy.md`).

## 4. Decision Engine -> Recovery

Response of `POST /api/decision/evaluate`:

```json
{
  "failure_type": "cpu_overload",
  "severity": "CRITICAL",
  "recommended_action": "scale_service",
  "reason": "High CPU utilization detected; scaling the affected service to redistribute load.",
  "confidence": 0.87
}
```

`recommended_action` is one of: `restart_service`, `scale_service`,
`redistribute_workload`, `cleanup_disk`, `no_action`. The full
type-to-action rule table is in `recovery_strategy.md`.

## 5. Recovery execution request / response

`POST /api/recovery/execute` -- request body is optional. Omit it to run
the full anomaly -> prediction -> decision chain automatically; supply
it to bypass that chain and run a specific action directly (used by the
demo flow and by tests):

```json
{
  "action": "cleanup_disk",
  "failure_type": "disk_exhaustion"
}
```

Response:

```json
{
  "success": true,
  "recovery_time_seconds": 5.14,
  "action": "scale_service",
  "failure_type": "cpu_overload",
  "before": { "...": "same shape as section 1" },
  "after": { "...": "same shape as section 1" },
  "execution_detail": {
    "success": true,
    "simulated": false,
    "target_replicas": 3,
    "started": ["autocura_test_worker_2", "autocura_test_worker_3"],
    "stopped": [],
    "message": "Scaled worker pool to 3 replicas."
  }
}
```

`execution_detail` varies per action -- `restart_service` returns
`{success, simulated, message}`; `cleanup_disk` returns
`{success, simulated, removed_items, freed_mb, message}`. `simulated:
true` means Docker wasn't reachable and the action was logged but not
actually executed against a container (see `architecture.md` section 6).

Persisted rows (`GET /api/recovery/history`) use a different, narrower
shape matching the `Recovery` table:

```json
{
  "id": 14,
  "failure_id": 9,
  "action": "scale_service",
  "started_at": "2026-01-15T10:30:00Z",
  "completed_at": "2026-01-15T10:30:05Z",
  "status": "success",
  "result": "Scaled worker pool to 3 replicas.",
  "recovery_time": 5.14
}
```

## 6. Alerts

`GET /api/alerts`:

```json
{
  "id": 3,
  "alert_type": "HIGH_CPU",
  "severity": "HIGH",
  "message": "CPU utilization exceeded threshold: 96.0% (limit 85.0%)",
  "source": "monitoring_engine",
  "timestamp": "2026-01-15T10:29:50Z",
  "acknowledged": false
}
```

`source` is one of `monitoring_engine` (threshold breach) or
`recovery_engine` (raised after `RECOVERY_RETRY_LIMIT` failed attempts).

## 7. Dashboard summary

`GET /api/dashboard/summary` -- the shape the top KPI cards bind to
directly:

```json
{
  "system_health": "healthy",
  "current_cpu": 42.3,
  "current_memory": 61.5,
  "current_disk": 38.0,
  "service_status": "running",
  "active_failures": 0,
  "recovery_success_rate": 0.87,
  "average_recovery_time_seconds": 4.9,
  "last_metric_timestamp": "2026-01-15T10:30:10Z"
}
```

`system_health` is computed, not stored: `critical` if any of
CPU/memory/disk exceeds 90%, `degraded` if there's an unresolved
failure, `healthy` otherwise.

## 8. Authentication

`POST /api/auth/register`: `{name, email, password}` returns `201` with
the created user (no password hash in the response).
`POST /api/auth/login`: `{email, password}` returns `{access_token,
token_type: "bearer"}`. Every other endpoint requires `Authorization:
Bearer <token>` except the health check and (deliberately, for the demo)
the monitoring/prediction/decision/recovery/simulation endpoints, which
are left open so the dashboard's live polling doesn't need a token
refresh loop mid-demo. Before
treating this as production-ready -- it isn't; a real deployment would
lock these down too.
