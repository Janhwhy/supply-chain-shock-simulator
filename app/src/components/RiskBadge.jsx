export function RiskBadge({ quadrant, riskBand }) {
  const text = quadrant || riskBand || 'Unknown';
  const lower = text.toLowerCase();
  let cls = 'risk-badge risk-badge--medium';
  if (lower.includes('critical')) cls = 'risk-badge risk-badge--critical';
  else if (lower.includes('high') || lower.includes('monitor')) cls = 'risk-badge risk-badge--high';
  else if (lower.includes('low') || lower.includes('routine')) cls = 'risk-badge risk-badge--low';
  return <span className={cls}>{text}</span>;
}
