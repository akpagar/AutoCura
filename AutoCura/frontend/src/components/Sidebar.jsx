import { NavLink } from "react-router-dom";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/monitoring", label: "Monitoring" },
  { to: "/predictions", label: "Predictions" },
  { to: "/simulation", label: "Simulation" },
  { to: "/recovery", label: "Recovery" },
  { to: "/alerts", label: "Alerts" },
  { to: "/logs", label: "Logs" },
];

export function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand-mark">●</span> AutoCura
      </div>
      {NAV_ITEMS.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
        >
          {item.label}
        </NavLink>
      ))}
    </aside>
  );
}
