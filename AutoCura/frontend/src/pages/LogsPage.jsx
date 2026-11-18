import { useState } from "react";
import { TopBar } from "../components/TopBar";
import { DataTable } from "../components/DataTable";
import { Badge } from "../components/Badge";
import { useInterval } from "../hooks/useInterval";
import { LogsAPI } from "../services/endpoints";
import { formatTimestamp } from "../utils/format";

export function LogsPage() {
  const [logs, setLogs] = useState([]);
  const [serviceFilter, setServiceFilter] = useState("");

  useInterval(async () => {
    try {
      const res = await LogsAPI.list(serviceFilter || null, 100);
      setLogs(res.data);
    } catch {
      // next poll retries
    }
  }, 6000);

  return (
    <>
      <TopBar title="Logs" />
      <div className="content">
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="field" style={{ maxWidth: 280, marginBottom: 0 }}>
            <label htmlFor="service-filter">Filter by service</label>
            <input
              id="service-filter"
              placeholder="e.g. monitoring_service"
              value={serviceFilter}
              onChange={(e) => setServiceFilter(e.target.value)}
            />
          </div>
        </div>

        <div className="card">
          <h2 className="section-title">System logs</h2>
          <DataTable
            emptyMessage="No log entries yet."
            columns={[
              { key: "timestamp", label: "Time", render: (r) => formatTimestamp(r.timestamp) },
              { key: "level", label: "Level", render: (r) => <Badge>{r.level}</Badge> },
              { key: "source", label: "Source" },
              { key: "service_name", label: "Service" },
              { key: "message", label: "Message" },
            ]}
            rows={logs}
          />
        </div>
      </div>
    </>
  );
}
