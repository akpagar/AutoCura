import { useState } from "react";
import { StatusPill } from "./StatusPill";
import { useAuth } from "../hooks/useAuth";
import { useInterval } from "../hooks/useInterval";
import { DashboardAPI } from "../services/endpoints";

const HEALTH_LABEL = {
  healthy: "System healthy",
  degraded: "System degraded",
  critical: "System critical",
};

export function TopBar({ title }) {
  const { logout } = useAuth();
  const [health, setHealth] = useState(null);

  useInterval(async () => {
    try {
      const response = await DashboardAPI.summary();
      setHealth(response.data.system_health);
    } catch {
      setHealth(null);
    }
  }, 2000);

  return (
    <header className="topbar">
      <h1>{title}</h1>
      <div className="btn-row" style={{ alignItems: "center" }}>
        {health && <StatusPill status={health} label={HEALTH_LABEL[health] || health} />}
        <button className="btn" onClick={logout}>
          Log out
        </button>
      </div>
    </header>
  );
}
