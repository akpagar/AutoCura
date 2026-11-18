import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { TopBar } from "../components/TopBar";
import { Badge } from "../components/Badge";
import { useInterval } from "../hooks/useInterval";
import { RecoveryAPI, SimulationAPI } from "../services/endpoints";
import { SCENARIOS } from "../utils/scenarios";
import { extractErrorMessage } from "../services/api";

const WATCH_SECONDS = 60;

export function SimulationPage() {
  const [active, setActive] = useState([]);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(null);
  const [recoveries, setRecoveries] = useState([]);
  const [watch, setWatch] = useState(null); // { label, baseId, startedAt }
  const [elapsed, setElapsed] = useState(0);
  const [outcome, setOutcome] = useState(null); // { seconds, ok }
  const latestId = useRef(0);

  const refresh = async () => {
    try {
      const [statusRes, histRes] = await Promise.all([SimulationAPI.status(), RecoveryAPI.history(8)]);
      setActive(statusRes.data.active_scenarios || []);
      setRecoveries(histRes.data);
      latestId.current = histRes.data.length ? Math.max(...histRes.data.map((r) => r.id)) : 0;

      if (watch) {
        const seconds = (Date.now() - watch.startedAt) / 1000;
        setElapsed(seconds);
        const fresh = histRes.data.filter((r) => r.id > watch.baseId);
        const finished = fresh.find((r) => r.status === "success");
        if (finished) {
          setOutcome({ seconds, ok: true, action: finished.action });
          setWatch(null);
        } else if (seconds > WATCH_SECONDS) {
          setOutcome({ seconds, ok: false });
          setWatch(null);
        }
      }
    } catch {
      // next poll retries
    }
  };

  // Fast polling only while a triggered scenario is being watched.
  useInterval(refresh, watch ? 1000 : 5000);

  const trigger = async (s) => {
    setBusy(s.key);
    setError("");
    setOutcome(null);
    try {
      const baseId = latestId.current;
      const res = await s.run();
      setMessage(res?.data?.message || `${s.label} triggered.`);
      setWatch({ label: s.label, baseId, startedAt: Date.now() });
      setElapsed(0);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setBusy(null);
    }
  };

  const reset = async () => {
    setBusy("reset");
    setError("");
    try {
      const res = await SimulationAPI.reset();
      setMessage(res?.data?.message || "Simulations reset.");
      setWatch(null);
      setOutcome(null);
      await refresh();
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setBusy(null);
    }
  };

  return (
    <>
      <TopBar title="Simulation" />
      <div className="content">
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-header">
            <h2>Controlled failure simulation</h2>
            <button className="btn danger" onClick={reset} disabled={busy === "reset"}>
              Reset all simulations
            </button>
          </div>
          <p style={{ marginBottom: 14 }}>
            Scenarios only change what AutoCura observes (and, for disk/service, touch its own
            scratch folder or controlled test container). Your real machine is never stressed.
            AutoCura detects the failure first (dashboard health turns critical and an alert is raised), then starts recovery after a short response delay; progress shows below. You can also use
            the <Link to="/recovery">Recovery page</Link> to run each step by hand.
          </p>
          <div className="btn-row">
            {SCENARIOS.map((s) => (
              <button key={s.key} className="btn" title={s.note} onClick={() => trigger(s)} disabled={busy === s.key}>
                {active.includes(s.scenario) ? "● " : ""}
                {s.label}
              </button>
            ))}
          </div>
          <p style={{ marginTop: 14 }}>Active: {active.length ? active.join(", ") : "none"}</p>
          {message && <p style={{ marginTop: 8 }}>{message}</p>}
          {error && <div className="error-text">{error}</div>}
        </div>

        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-header">
            <h2>Auto-recovery progress</h2>
          </div>
          {watch && (
            <p>
              Watching <strong style={{ color: "var(--text)" }}>{watch.label}</strong>… {elapsed.toFixed(0)}s elapsed
            </p>
          )}
          {!watch && outcome && outcome.ok && (
            <p>
              Recovered automatically in about <strong style={{ color: "var(--text)" }}>{outcome.seconds.toFixed(1)}s</strong>{" "}
              using <span className="mono">{outcome.action}</span>.
            </p>
          )}
          {!watch && outcome && !outcome.ok && (
            <p>No successful recovery within {WATCH_SECONDS}s. Check the Recovery page and Alerts for details.</p>
          )}
          {!watch && !outcome && <p>Trigger a scenario above to watch AutoCura detect and recover from it.</p>}
        </div>

        <div className="card">
          <div className="card-header">
            <h2>Latest recovery attempts</h2>
          </div>
          {recoveries.length === 0 ? (
            <p>No recovery attempts yet.</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Action</th>
                  <th>Status</th>
                  <th>Time (s)</th>
                  <th>Result</th>
                </tr>
              </thead>
              <tbody>
                {recoveries.map((r) => (
                  <tr key={r.id}>
                    <td>{r.id}</td>
                    <td className="mono">{r.action}</td>
                    <td><Badge>{r.status}</Badge></td>
                    <td>{Number(r.recovery_time).toFixed(2)}</td>
                    <td>{r.result}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </>
  );
}
