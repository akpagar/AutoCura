export function KpiCard({ label, value, status = "healthy", suffix = "" }) {
  return (
    <div className={`kpi-card status-${status}`}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">
        {value}
        {suffix && <span style={{ fontSize: 14, color: "var(--text-secondary)", marginLeft: 4 }}>{suffix}</span>}
      </div>
    </div>
  );
}
