import { useState } from "react";
import { TopBar } from "../components/TopBar";
import { DataTable } from "../components/DataTable";
import { Badge } from "../components/Badge";
import { useInterval } from "../hooks/useInterval";
import { DecisionAPI, RecoveryAPI, SimulationAPI } from "../services/endpoints";
import { extractErrorMessage } from "../services/api";
import { formatTimestamp } from "../utils/format";
import { SCENARIOS } from "../utils/scenarios";

export function RecoveryPage() {
  const [history, setHistory] = useState([]);
  const [decision, setDecision] = useState(null);
  const [recoveryResult, setRecoveryResult] = useState(null);
  const [activeSimulations, setActiveSimulations] = useState([]);
  const [error, setError] = useState("");
  const [busyKey, setBusyKey] = useState(null);

  useInterval(async () => {
    try {
      const [historyRes, statusRes] = await Promise.all([RecoveryAPI.history(15), SimulationAPI.status()]);
      setHistory(historyRes.data);
      setActiveSimulations(statusRes.data.active_scenarios || []);
    } catch {
      // next poll retries
    }
  }, 6000);

  const runWithBusy = async (key, fn) => {
    setBusyKey(key);
    setError("");
    try {
      await fn();
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setBusyKey(null);
    }
  };

  const triggerScenario = (scenario) =>
    runWithBusy(scenario.key, async () => {
      await scenario.run();
    });

  const evaluateDecision = () =>
    runWithBusy("decision", async () => {
      const res = await DecisionAPI.evaluate();
      setDecision(res.data);
    });

  const executeRecovery = () =>
    runWithBusy("recovery", async () => {
      const res = await RecoveryAPI.execute();
      setRecoveryResult(res.data);
    });

  const resetSimulation = () =>
    runWithBusy("reset", async () => {
      await SimulationAPI.reset();
      setActiveSimulations([]);
      setDecision(null);
      setRecoveryResult(null);
    });

  return (
    <>
      <TopBar title="Recovery" />
      <div className="content">
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-header">
            <h2>1. Trigger a controlled test failure</h2>
            {activeSimulations.length > 0 && (
              <button className="btn danger" onClick={resetSimulation} disabled={busyKey === "reset"}>
                Reset all simulations
              </button>
            )}
          </div>
          <p style={{ marginBottom: 14 }}>
            These only ever affect AutoCura's own controlled test environment -- never your real
            machine. CPU/memory/disk/network scenarios change what the monitoring layer reports;
            service failure actually stops a controlled Docker container, if one is running.
          </p>
          <div className="btn-row">
            {SCENARIOS.map((s) => (
              <button
                key={s.key}
                className="btn"
                onClick={() => triggerScenario(s)}
                disabled={busyKey === s.key}
              >
                {activeSimulations.includes(s.scenario) ? "● " : ""}
                {s.label}
              </button>
            ))}
          </div>
          {error && <div className="error-text">{error}</div>}
        </div>

        <div className="two-col">
          <div className="card">
            <div className="card-header">
              <h2>2. Evaluate</h2>
              <button className="btn" onClick={evaluateDecision} disabled={busyKey === "decision"}>
                {busyKey === "decision" ? "Evaluating…" : "Run decision engine"}
              </button>
            </div>
            {decision ? (
              <div>
                <p>
                  <strong style={{ color: "var(--text)" }}>{decision.failure_type}</strong> detected at{" "}
                  <Badge>{decision.severity}</Badge> severity.
                </p>
                <p style={{ marginTop: 8 }}>{decision.reason}</p>
                <p style={{ marginTop: 8 }}>
                  Recommended action: <span className="mono">{decision.recommended_action}</span>
                </p>
              </div>
            ) : (
              <p>Run the decision engine to see what AutoCura would do about the current state.</p>
            )}
          </div>

          <div className="card">
            <div className="card-header">
              <h2>3. Recover</h2>
              <button className="btn primary" onClick={executeRecovery} disabled={busyKey === "recovery"}>
                {busyKey === "recovery" ? "Recovering…" : "Execute recovery"}
              </button>
            </div>
            {recoveryResult ? (
              <div>
                <p>
                  Action <span className="mono">{recoveryResult.action}</span> —{" "}
                  <Badge>{recoveryResult.success ? "success" : "failed"}</Badge>
                </p>
                <p style={{ marginTop: 8 }}>Recovery time: {recoveryResult.recovery_time_seconds}s</p>
                <p style={{ marginTop: 8 }}>{recoveryResult.execution_detail?.message}</p>
              </div>
            ) : (
              <p>
                Runs the full decide-&gt;act-&gt;verify chain and executes the recommended action
                against the controlled test environment.
              </p>
            )}
          </div>
        </div>

        <div className="card" style={{ marginTop: 16 }}>
          <h2 className="section-title">Recovery history</h2>
          <DataTable
            emptyMessage="No recovery actions have run yet."
            columns={[
              { key: "started_at", label: "Started", render: (r) => formatTimestamp(r.started_at) },
              { key: "action", label: "Action", mono: true },
              { key: "status", label: "Result", render: (r) => <Badge>{r.status}</Badge> },
              { key: "recovery_time", label: "Time", render: (r) => `${r.recovery_time}s` },
              { key: "result", label: "Detail" },
            ]}
            rows={history}
          />
        </div>
      </div>
    </>
  );
}
