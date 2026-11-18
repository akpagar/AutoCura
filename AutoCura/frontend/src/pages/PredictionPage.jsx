import { useState } from "react";
import { TopBar } from "../components/TopBar";
import { DataTable } from "../components/DataTable";
import { Badge } from "../components/Badge";
import { useInterval } from "../hooks/useInterval";
import { PredictionAPI } from "../services/endpoints";
import { extractErrorMessage } from "../services/api";
import { formatTimestamp } from "../utils/format";

export function PredictionPage() {
  const [history, setHistory] = useState([]);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useInterval(async () => {
    try {
      const res = await PredictionAPI.history(20);
      setHistory(res.data);
    } catch {
      // next poll retries
    }
  }, 8000);

  const runPrediction = async () => {
    setBusy(true);
    setError("");
    try {
      const res = await PredictionAPI.predict();
      setResult(res.data);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <TopBar title="Predictions" />
      <div className="content">
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-header">
            <h2>Run a prediction</h2>
            <button className="btn primary" onClick={runPrediction} disabled={busy}>
              {busy ? "Running…" : "Run on live metrics"}
            </button>
          </div>
          <p>
            Runs the trained classifier against the current live monitoring sample and the
            anomaly detector (thresholds + Isolation Forest) together.
          </p>
          {error && <div className="error-text">{error}</div>}

          {result && (
            <div className="two-col" style={{ marginTop: 16 }}>
              <div>
                <div className="kpi-label">Predicted failure type</div>
                <div className="kpi-value" style={{ fontSize: 20 }}>{result.failure_type}</div>
              </div>
              <div>
                <div className="kpi-label">Severity</div>
                <div style={{ marginTop: 6 }}>
                  <Badge>{result.severity}</Badge>
                </div>
              </div>
              <div>
                <div className="kpi-label">Failure probability</div>
                <div className="kpi-value" style={{ fontSize: 20 }}>{(result.failure_probability * 100).toFixed(1)}%</div>
              </div>
              <div>
                <div className="kpi-label">Confidence</div>
                <div className="kpi-value" style={{ fontSize: 20 }}>{(result.confidence * 100).toFixed(1)}%</div>
              </div>
              {result.anomaly?.is_anomaly && (
                <div style={{ gridColumn: "1 / -1" }}>
                  <div className="kpi-label">Anomaly signals</div>
                  <p style={{ marginTop: 4 }}>
                    {result.anomaly.threshold_reasons.join(", ") || "No threshold breaches"}
                    {result.anomaly.isolation_forest_flagged ? " · flagged by Isolation Forest" : ""}
                  </p>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="card">
          <h2 className="section-title">Prediction history</h2>
          <DataTable
            emptyMessage="No predictions have been run yet."
            columns={[
              { key: "timestamp", label: "Time", render: (r) => formatTimestamp(r.timestamp) },
              { key: "predicted_failure_type", label: "Type" },
              { key: "severity", label: "Severity", render: (r) => <Badge>{r.severity}</Badge> },
              {
                key: "failure_probability",
                label: "Probability",
                render: (r) => `${(r.failure_probability * 100).toFixed(1)}%`,
              },
              { key: "confidence", label: "Confidence", render: (r) => `${(r.confidence * 100).toFixed(1)}%` },
            ]}
            rows={history}
          />
        </div>
      </div>
    </>
  );
}
