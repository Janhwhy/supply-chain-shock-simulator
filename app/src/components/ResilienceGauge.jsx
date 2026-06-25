/** Circle SVG gauge showing a 0–1 risk score as a percentage arc */
export function ResilienceGauge({ label, value, color }) {
  const pct = Math.round((value ?? 0) * 100);
  const strokeDasharray = `${pct}, 100`;

  function statusLabel(p) {
    if (p >= 80) return 'Critical';
    if (p >= 60) return 'Elevated';
    if (p >= 40) return 'Moderate';
    if (p >= 20) return 'Stable';
    return 'Low';
  }

  return (
    <div className="gauge-card">
      <span className="gauge-card__label label-caps">{label}</span>
      <div style={{ position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center', marginTop: 40 }}>
        <svg className="gauge-card__svg" viewBox="0 0 36 36">
          <path
            stroke="#31353a" fill="none" strokeWidth="3"
            d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
          />
          <path
            stroke={color} fill="none" strokeWidth="3"
            strokeDasharray={strokeDasharray}
            d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
          />
        </svg>
        <span className="gauge-card__center headline-lg" style={{ color, position: 'absolute' }}>{pct}</span>
      </div>
      <span className="gauge-card__status data-mono" style={{ color }}>{statusLabel(pct)}</span>
    </div>
  );
}
