import { useState } from "react";
import { KpiCard } from "../components/KpiCard";
import { MetricLineChart } from "../components/MetricLineChart";
import { DataTable } from "../components/DataTable";
import { Badge } from "../components/Badge";
import { TopBar } from "../components/TopBar";
import { useInterval } from "../hooks/useInterval";
import { DashboardAPI } from "../services/endpoints";
import { formatPercent, formatTimestamp } from "../utils/format";

export function DashboardPage() {
  const [summary, setSummary] = useState(null);
  const [series, setSeries] = useState([]);
  const [failures, setFailures] = useState([]);
  const [recoveries, setRecoveries] = useState([]);

  useInterval(async () => {
    try {
      const [summaryRes, metricsRes, failuresRes, recoveriesRes] = await Promise.all([
        DashboardAPI.summary(),
        DashboardAPI.metrics(60),
        DashboardAPI.failures(6),
        DashboardAPI.recoveries(6),
      ]);
      setSummary(summaryRes.data);
      setSeries(metricsRes.data);
      setFailures(failuresRes.data);
      setRecoveries(recoveriesRes.data);
    } catch {
      // Transient fetch failure -- the next poll tick will retry.
    }
  }, 2000);

  return (
    <>
      <TopBar title="Dashboard" />
      <div className="content">
        <div className="kpi-grid">
          <KpiCard
            label="System health"
            value={summary?.system_health ?? "—"}
            status={summary?.system_health ?? "healthy"}
          />
          <KpiCard
            label="Current CPU"
            value={formatPercent(summary?.current_cpu)}
            status={summary?.current_cpu > 90 ? "critical" : summary?.current_cpu > 75 ? "degraded" : "healthy"}
          />
          <KpiCard
            label="Current memory"
            value={formatPercent(summary?.current_memory)}
            status={summary?.current_memory > 90 ? "critical" : summary?.current_memory > 75 ? "degraded" : "healthy"}
          />
          <KpiCard label="Active failures" value={summary?.active_failures ?? "—"} status={summary?.active_failures > 0 ? "degraded" : "healthy"} />
          <KpiCard
            label="Recovery success rate"
            value={summary?.recovery_success_rate != null ? formatPercent(summary.recovery_success_rate * 100) : "—"}
          />
          <KpiCard
            label="Avg. recovery time"
            value={summary?.average_recovery_time_seconds != null ? `${summary.average_recovery_time_seconds}s` : "—"}
          />
        </div>

        <div className="two-col">
          <div className="card">
            <div className="card-header">
              <h2>CPU &amp; memory</h2>
            </div>
            <MetricLineChart
              data={series}
              unit="%"
              lines={[
                { key: "cpu_usage", color: "var(--healthy)", label: "CPU" },
                { key: "memory_usage", color: "var(--info)", label: "Memory" },
              ]}
            />
          </div>
          <div className="card">
            <div className="card-header">
              <h2>Disk &amp; latency</h2>
            </div>
            <MetricLineChart
              data={series}
              lines={[
                { key: "disk_usage", color: "var(--degraded)", label: "Disk %" },
                { key: "latency", color: "var(--critical)", label: "Latency (ms)" },
              ]}
            />
          </div>
        </div>

        <div className="two-col">
          <div className="card">
            <h2 className="section-title">Recent failures</h2>
            <DataTable
              emptyMessage="No failures recorded -- system has been healthy."
              columns={[
                { key: "detected_at", label: "Detected", render: (r) => formatTimestamp(r.detected_at) },
                { key: "failure_type", label: "Type" },
                { key: "severity", label: "Severity", render: (r) => <Badge>{r.severity}</Badge> },
                { key: "status", label: "Status", render: (r) => <Badge>{r.status}</Badge> },
              ]}
              rows={failures}
            />
          </div>
          <div className="card">
            <h2 className="section-title">Recent recovery actions</h2>
            <DataTable
              emptyMessage="No recovery actions have run yet."
              columns={[
                { key: "started_at", label: "Started", render: (r) => formatTimestamp(r.started_at) },
                { key: "action", label: "Action" },
                { key: "status", label: "Result", render: (r) => <Badge>{r.status}</Badge> },
                { key: "recovery_time", label: "Time", render: (r) => `${r.recovery_time}s` },
              ]}
              rows={recoveries}
            />
          </div>
        </div>
      </div>
    </>
  );
}
