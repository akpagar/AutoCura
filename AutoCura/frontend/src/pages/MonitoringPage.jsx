import { useState } from "react";
import { TopBar } from "../components/TopBar";
import { KpiCard } from "../components/KpiCard";
import { MetricLineChart } from "../components/MetricLineChart";
import { useInterval } from "../hooks/useInterval";
import { MonitoringAPI } from "../services/endpoints";
import { extractErrorMessage } from "../services/api";
import { formatPercent } from "../utils/format";

export function MonitoringPage() {
  const [current, setCurrent] = useState(null);
  const [history, setHistory] = useState([]);
  const [active, setActive] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useInterval(async () => {
    try {
      const [currentRes, historyRes, healthRes] = await Promise.all([
        MonitoringAPI.current(),
        MonitoringAPI.history(60),
        MonitoringAPI.health(),
      ]);
      setCurrent(currentRes.data);
      setHistory(historyRes.data);
      setActive(healthRes.data.monitoring_active);
    } catch {
      // next poll retries
    }
  }, 5000);

  const toggle = async () => {
    setBusy(true);
    setError("");
    try {
      if (active) {
        await MonitoringAPI.stop();
      } else {
        await MonitoringAPI.start();
      }
      const healthRes = await MonitoringAPI.health();
      setActive(healthRes.data.monitoring_active);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <TopBar title="Monitoring" />
      <div className="content">
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-header">
            <h2>Background collector</h2>
            <div className="btn-row">
              <span className={`status-pill ${active ? "healthy" : "degraded"}`}>
                <span className="dot" />
                {active ? "Running" : "Stopped"}
              </span>
              <button className="btn" onClick={toggle} disabled={busy}>
                {active ? "Stop collector" : "Start collector"}
              </button>
            </div>
          </div>
          <p>
            Collects CPU, memory, disk, network, and service-health samples on a fixed interval and
            writes them to the metrics table. The automated recovery pipeline (Phase 6) runs after
            each cycle this collector completes.
          </p>
          {error && <div className="error-text">{error}</div>}
        </div>

        <div className="kpi-grid">
          <KpiCard label="CPU" value={formatPercent(current?.cpu_usage)} status={current?.cpu_usage > 90 ? "critical" : current?.cpu_usage > 75 ? "degraded" : "healthy"} />
          <KpiCard label="Memory" value={formatPercent(current?.memory_usage)} status={current?.memory_usage > 90 ? "critical" : current?.memory_usage > 75 ? "degraded" : "healthy"} />
          <KpiCard label="Disk" value={formatPercent(current?.disk_usage)} status={current?.disk_usage > 90 ? "critical" : current?.disk_usage > 75 ? "degraded" : "healthy"} />
          <KpiCard label="Service status" value={current?.service_status ?? "—"} status={current?.service_status === "running" ? "healthy" : "critical"} />
        </div>

        <div className="two-col">
          <div className="card">
            <h2 className="section-title">CPU &amp; memory over time</h2>
            <MetricLineChart
              data={history}
              unit="%"
              lines={[
                { key: "cpu_usage", color: "var(--healthy)", label: "CPU" },
                { key: "memory_usage", color: "var(--info)", label: "Memory" },
              ]}
            />
          </div>
          <div className="card">
            <h2 className="section-title">Network throughput</h2>
            <MetricLineChart
              data={history}
              lines={[
                { key: "network_in", color: "var(--healthy)", label: "In (bytes)" },
                { key: "network_out", color: "var(--degraded)", label: "Out (bytes)" },
              ]}
            />
          </div>
        </div>
      </div>
    </>
  );
}
