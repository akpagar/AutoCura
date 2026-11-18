export function StatusPill({ status, label }) {
  return (
    <span className={`status-pill ${status}`}>
      <span className="dot" />
      {label}
    </span>
  );
}
