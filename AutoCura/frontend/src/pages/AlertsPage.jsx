import { useState } from "react";
import { TopBar } from "../components/TopBar";
import { DataTable } from "../components/DataTable";
import { Badge } from "../components/Badge";
import { useInterval } from "../hooks/useInterval";
import { AlertsAPI } from "../services/endpoints";
import { extractErrorMessage } from "../services/api";
import { formatTimestamp } from "../utils/format";

export function AlertsPage() {
  const [alerts, setAlerts] = useState([]);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState(null);

  const refresh = async () => {
    const res = await AlertsAPI.list(50);
    setAlerts(res.data);
  };

  useInterval(async () => {
    try {
      await refresh();
    } catch {
      // next poll retries
    }
  }, 6000);

  const acknowledge = async (id) => {
    setBusyId(id);
    setError("");
    try {
      await AlertsAPI.acknowledge(id);
      await refresh();
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setBusyId(null);
    }
  };

  return (
    <>
      <TopBar title="Alerts" />
      <div className="content">
        {error && <div className="error-text" style={{ marginBottom: 12 }}>{error}</div>}
        <div className="card">
          <h2 className="section-title">All alerts</h2>
          <DataTable
            emptyMessage="No alerts have been raised."
            columns={[
              { key: "timestamp", label: "Time", render: (r) => formatTimestamp(r.timestamp) },
              { key: "alert_type", label: "Type" },
              { key: "severity", label: "Severity", render: (r) => <Badge>{r.severity}</Badge> },
              { key: "message", label: "Message" },
              { key: "source", label: "Source" },
              {
                key: "acknowledged",
                label: "Status",
                render: (r) =>
                  r.acknowledged ? (
                    <Badge>acknowledged</Badge>
                  ) : (
                    <button className="btn" onClick={() => acknowledge(r.id)} disabled={busyId === r.id}>
                      {busyId === r.id ? "…" : "Acknowledge"}
                    </button>
                  ),
              },
            ]}
            rows={alerts}
          />
        </div>
      </div>
    </>
  );
}
