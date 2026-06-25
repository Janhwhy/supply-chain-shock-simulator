import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { RiskBadge } from '../components/RiskBadge';
import { LoadingSpinner, ErrorBox } from '../components/LoadingSpinner';

function fmt(n) {
  if (n == null) return '—';
  if (Math.abs(n) >= 1e7) return `₹${(n / 1e7).toFixed(2)} Cr`;
  if (Math.abs(n) >= 1e5) return `₹${(n / 1e5).toFixed(2)} L`;
  return `₹${n.toFixed(0)}`;
}

function dominantRisk(row) {
  const keys = { dependency_risk: 'Dependency', geo_risk: 'Geographic', reliability_risk: 'Reliability', substitutability_risk: 'Substitutability' };
  let best = null, bestVal = -1;
  for (const [k, label] of Object.entries(keys)) {
    if ((row[k] ?? -1) > bestVal) { bestVal = row[k]; best = label; }
  }
  return best || '—';
}

function payback(row) {
  if (!row.estimated_cost || !row.p95_impact || !row.roi) return '—';
  const months = row.estimated_cost / (row.p95_impact * Math.max(row.roi, 0.01));
  return `${months.toFixed(1)} mo`;
}

export function MitigationPlaybook() {
  const [playbook, setPlaybook] = useState([]);
  const [kpis, setKpis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState('');

  useEffect(() => {
    Promise.all([api.playbook(), api.kpis()])
      .then(([p, k]) => { setPlaybook(p); setKpis(k); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });
  }, []);

  if (loading) return <LoadingSpinner message="Loading mitigation playbook…" />;
  if (error)   return <ErrorBox message={error} />;

  const filtered = filter
    ? playbook.filter(r => r.priority_quadrant?.toLowerCase().includes(filter.toLowerCase()))
    : playbook;

  // Bar chart: top 5 by roi
  const top5 = [...playbook].sort((a, b) => (b.roi || 0) - (a.roi || 0)).slice(0, 5);
  const maxCost = Math.max(...top5.map(r => r.estimated_cost || 0), 1);
  const maxRed  = Math.max(...top5.map(r => r.p95_impact || 0), 1);

  // Donut chart: action type distribution
  const actionGroups = {};
  playbook.forEach(r => {
    const key = r.recommended_action?.split(' ')[0] || 'Other';
    actionGroups[key] = (actionGroups[key] || 0) + 1;
  });
  const actionEntries = Object.entries(actionGroups).sort((a, b) => b[1] - a[1]).slice(0, 4);
  const totalActions = actionEntries.reduce((s, [, v]) => s + v, 0) || 1;
  const donutColors = ['#003d5c', '#ffa600', '#ff6b59', '#dd4d88'];

  let cumPct = 0;
  const donutSegments = actionEntries.map(([label, count], i) => {
    const pct = (count / totalActions) * 100;
    const seg = { label, pct, start: cumPct, color: donutColors[i % donutColors.length] };
    cumPct += pct;
    return seg;
  });

  function quadrantBadgeClass(q) {
    if (!q) return '';
    const lower = q.toLowerCase();
    if (lower.includes('critical')) return 'risk-badge risk-badge--critical';
    if (lower.includes('monitor')) return 'risk-badge risk-badge--high';
    if (lower.includes('contingency')) return 'risk-badge risk-badge--high';
    return 'risk-badge risk-badge--low';
  }

  function exportCSV() {
    const headers = ['supplier_name','priority_quadrant','recommended_action','scenario','estimated_cost','p95_impact','roi'];
    const rows = [headers, ...playbook.map(r => headers.map(h => r[h] ?? ''))];
    const csv = rows.map(r => r.join(',')).join('\n');
    const a = document.createElement('a'); a.href = 'data:text/csv;charset=utf-8,' + encodeURIComponent(csv); a.download = 'mitigation_playbook.csv'; a.click();
  }

  return (
    <>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 24 }}>
        <div>
          <h2 className="headline-lg">Mitigation Playbook View</h2>
          <p className="body-sm" style={{ color: 'var(--on-surface-variant)', marginTop: 4 }}>Prioritized action matrix for supplier risk reduction.</p>
        </div>
        <button onClick={exportCSV} style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'var(--primary-container)', color: 'var(--on-primary-container)', padding: '8px 16px', borderRadius: 4, fontSize: 14, fontWeight: 700, border: '1px solid var(--primary-container)' }}>
          <span className="material-symbols-outlined" style={{ fontSize: 18 }}>download</span>
          Export Playbook
        </button>
      </div>

      {/* Summary Banner */}
      <div className="playbook-banner">
        <div className="playbook-banner__item">
          <div className="playbook-banner__label">Total Budget Allocated</div>
          <div className="playbook-banner__value">{fmt(kpis?.recommended_budget)}</div>
        </div>
        <div className="playbook-banner__item">
          <div className="playbook-banner__label">Total Risk Eliminated</div>
          <div className="playbook-banner__value" style={{ color: '#003d5c' }}>{fmt(kpis?.total_risk_eliminated)}</div>
        </div>
        <div className="playbook-banner__item" style={{ borderRight: 'none' }}>
          <div className="playbook-banner__label">Portfolio ROI Matrix</div>
          <div className="playbook-banner__value" style={{ color: '#ffa600' }}>
            {kpis?.portfolio_roi != null ? `${kpis.portfolio_roi.toFixed(2)}×` : '—'}
          </div>
        </div>
      </div>

      {/* Filter bar */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
        {['', 'Critical Priority', 'Monitor Closely', 'Contingency Plan', 'Routine Review'].map(q => (
          <button key={q}
            onClick={() => setFilter(q)}
            style={{ padding: '4px 12px', borderRadius: 100, fontSize: 12, fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase', border: '1px solid', borderColor: filter === q ? 'var(--primary)' : 'var(--outline-variant)', background: filter === q ? 'var(--primary-container)' : 'transparent', color: filter === q ? 'var(--on-primary-container)' : 'var(--on-surface-variant)' }}
          >{q || 'All'}</button>
        ))}
      </div>

      {/* Main Table */}
      <div className="card" style={{ marginBottom: 24, overflow: 'auto' }}>
        <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--outline-variant)', background: 'var(--surface-container-high)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2 className="title-md">Active Interventions</h2>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span className="material-symbols-outlined" style={{ color: 'var(--on-surface-variant)', cursor: 'pointer', fontSize: 20 }}>filter_list</span>
            <span className="material-symbols-outlined" style={{ color: 'var(--on-surface-variant)', cursor: 'pointer', fontSize: 20 }}>more_vert</span>
          </div>
        </div>
        <table className="data-table" style={{ minWidth: 1200 }}>
          <thead style={{ background: 'var(--surface-container-low)' }}>
            <tr>
              <th>Supplier Name</th>
              <th>Priority Quadrant</th>
              <th>Dominant Risk Factor</th>
              <th>Recommended Action</th>
              <th>Action Description</th>
              <th style={{ textAlign: 'right' }}>Action Cost</th>
              <th style={{ textAlign: 'right' }}>Expected Annual Loss</th>
              <th style={{ textAlign: 'right' }}>Risk Reduction</th>
              <th style={{ textAlign: 'right' }}>ROI ↓</th>
              <th style={{ textAlign: 'right' }}>Payback</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((r, i) => {
              const isCrit = r.priority_quadrant?.toLowerCase().includes('critical');
              const isMonitor = r.priority_quadrant?.toLowerCase().includes('monitor');
              const rowBg = isCrit ? 'rgba(255,107,89,0.06)' : isMonitor ? 'rgba(255,166,0,0.06)' : 'transparent';
              
              // Payback period years formatting
              let paybackStr = '—';
              if (r.payback_period_years != null) {
                paybackStr = r.payback_period_years === Infinity ? '∞' : `${r.payback_period_years.toFixed(2)} yrs`;
              } else if (r.estimated_cost && r.p95_impact && r.roi) {
                const yrs = r.estimated_cost / (r.p95_impact * Math.max(r.roi, 0.01)) / 12.0;
                paybackStr = `${yrs.toFixed(2)} yrs`;
              }

              return (
                <tr key={i} style={{ background: rowBg }}>
                  <td style={{ fontWeight: 600 }}>{r.supplier_name || `SUP-${r.supplier_id}`}</td>
                  <td>{r.priority_quadrant ? <RiskBadge quadrant={r.priority_quadrant} /> : '—'}</td>
                  <td className="body-sm" style={{ color: 'var(--on-surface-variant)' }}>{r.dominant_risk_label || dominantRisk(r)}</td>
                  <td><strong>{r.recommended_action}</strong></td>
                  <td className="body-xs" style={{ color: 'var(--on-surface-variant)', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={r.action_description}>{r.action_description || '—'}</td>
                  <td className="data-mono" style={{ textAlign: 'right' }}>{fmt(r.action_cost ?? r.estimated_cost)}</td>
                  <td className="data-mono" style={{ textAlign: 'right' }}>{fmt(r.expected_annual_loss ?? r.p95_impact)}</td>
                  <td className="data-mono" style={{ textAlign: 'right', color: 'var(--primary)' }}>{fmt(r.risk_reduction)}</td>
                  <td className="data-mono" style={{ textAlign: 'right', color: '#ffa600', fontWeight: 700 }}>{r.roi != null ? `${r.roi.toFixed(2)}×` : '—'}</td>
                  <td className="data-mono" style={{ textAlign: 'right' }}>{paybackStr}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Charts */}
      <div style={{ display: 'grid', gridTemplateColumns: '8fr 4fr', gap: 24 }}>
        {/* Bar chart: Cost vs Risk Reduction */}
        <div className="card card--p">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h3 className="title-md">Action Cost vs Risk Exposure (Top 5 by ROI)</h3>
            <div style={{ display: 'flex', gap: 12 }}>
              {[['var(--outline)','Cost'],['#003d5c','P95 Exposure']].map(([color, label]) => (
                <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <div style={{ width: 12, height: 12, background: color, borderRadius: 2 }} />
                  <span className="label-caps" style={{ color: 'var(--on-surface-variant)' }}>{label}</span>
                </div>
              ))}
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-around', height: 200, paddingBottom: 32, borderBottom: '1px solid var(--outline-variant)', borderLeft: '1px solid var(--outline-variant)', paddingTop: 24, position: 'relative' }}>
            {[0.25, 0.5, 0.75].map(pct => (
              <div key={pct} style={{ position: 'absolute', left: 0, right: 0, bottom: `${pct * 100 + 32}%`, height: 1, background: 'rgba(64,71,81,0.3)', pointerEvents: 'none' }} />
            ))}
            {top5.map((r, i) => {
              const costH = (r.estimated_cost / maxCost) * 80;
              const redH  = (r.p95_impact / maxRed) * 80;
              const name  = (r.supplier_name || `SUP-${r.supplier_id}`).split(' ')[0];
              return (
                <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, position: 'relative', zIndex: 1, width: 60 }}>
                  <div style={{ display: 'flex', alignItems: 'flex-end', gap: 2, height: 160 }}>
                    <div style={{ width: 14, background: 'var(--outline)', borderRadius: '4px 4px 0 0', height: `${costH}%` }} />
                    <div style={{ width: 14, background: '#003d5c', borderRadius: '4px 4px 0 0', height: `${redH}%`, boxShadow: '0 0 10px rgba(0,61,92,0.2)' }} />
                  </div>
                  <span className="label-caps" style={{ color: 'var(--on-surface-variant)', fontSize: 10 }}>{name}</span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Donut chart: Action Type Distribution */}
        <div className="card card--p" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <h3 className="title-md" style={{ width: '100%', textAlign: 'left', marginBottom: 24 }}>Action Type Distribution</h3>
          <div style={{ position: 'relative', width: 160, height: 160 }}>
            <svg viewBox="0 0 36 36" style={{ width: '100%', height: '100%', transform: 'rotate(-90deg)' }}>
              {donutSegments.map((seg, i) => (
                <circle key={i}
                  cx="18" cy="18" r="15.9155"
                  fill="none"
                  stroke={seg.color}
                  strokeWidth="3.5"
                  strokeDasharray={`${seg.pct} ${100 - seg.pct}`}
                  strokeDashoffset={`-${seg.start}`}
                />
              ))}
            </svg>
            <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center' }}>
              <div style={{ fontSize: 24, fontWeight: 700 }}>{playbook.length}</div>
              <div className="label-caps" style={{ color: 'var(--on-surface-variant)', fontSize: 10 }}>Actions</div>
            </div>
          </div>
          <div style={{ width: '100%', marginTop: 16, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px 4px' }}>
            {donutSegments.map((seg, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <div style={{ width: 12, height: 12, borderRadius: 2, background: seg.color, flexShrink: 0 }} />
                <span className="label-caps" style={{ color: 'var(--on-surface-variant)', fontSize: 10 }}>{seg.label} ({seg.pct.toFixed(0)}%)</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}
