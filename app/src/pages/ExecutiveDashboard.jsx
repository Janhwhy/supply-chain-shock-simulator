import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { RiskBadge } from '../components/RiskBadge';
import { LoadingSpinner, ErrorBox } from '../components/LoadingSpinner';

function fmt(n) {
  if (n == null) return '—';
  if (Math.abs(n) >= 1e7) return `₹${(n / 1e7).toFixed(1)} Cr`;
  if (Math.abs(n) >= 1e5) return `₹${(n / 1e5).toFixed(1)} L`;
  return `₹${n.toFixed(0)}`;
}

function ResilienceBar({ score, color }) {
  const w = score != null ? Math.min(100, Math.max(0, (1 - score) * 100)) : 50;
  return (
    <div className="resilience-bar" style={{ width: 120 }}>
      <div className="resilience-bar__fill" style={{ width: `${w}%`, background: color }} />
    </div>
  );
}

function bandColor(band) {
  if (!band) return '#8a919c';
  const b = band.toLowerCase();
  if (b === 'critical') return '#ff6b59';
  if (b === 'high')     return '#ffa600';
  if (b === 'medium')   return '#464c89';
  return '#4299e1';
}

export function ExecutiveDashboard() {
  const navigate = useNavigate();
  const [kpis, setKpis] = useState(null);
  const [suppliers, setSuppliers] = useState([]);
  const [matrix, setMatrix] = useState([]);
  const [playbook, setPlaybook] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([api.kpis(), api.suppliers(), api.priorityMatrix(), api.playbook()])
      .then(([k, s, m, pb]) => {
        setKpis(k);
        setSuppliers(s);
        setMatrix(m);
        setPlaybook(pb);
        setLoading(false);
      })
      .catch(e => { setError(e.message); setLoading(false); });
  }, []);

  if (loading) return <LoadingSpinner message="Loading executive summary…" />;
  if (error)   return <ErrorBox message={error} />;

  const topSuppliers = [...suppliers]
    .sort((a, b) => (b.total_p95_exposure || 0) - (a.total_p95_exposure || 0))
    .slice(0, 8);

  // Build scatter points: normalize resilience_score and total_p95_exposure
  const maxExp = Math.max(...matrix.map(r => r.total_p95_exposure || 0), 1);

  // Top 3 actions by ROI
  const top3Actions = [...playbook]
    .filter(r => r.roi != null && r.roi > 0)
    .sort((a, b) => (b.roi || 0) - (a.roi || 0))
    .slice(0, 3);

  const ACTION_ICONS = {
    'Dual-Sourcing': 'hub',
    'Safety Stock': 'inventory',
    'Geographic Diversification': 'language',
    'Supplier Development': 'groups',
    'Quarterly Monitoring': 'monitoring',
  };

  function getActionIcon(action) {
    if (!action) return 'bolt';
    for (const [key, icon] of Object.entries(ACTION_ICONS)) {
      if (action.includes(key)) return icon;
    }
    return 'bolt';
  }

  return (
    <>
      <div className="page-header">
        <h2 className="headline-lg">Executive Summary</h2>
      </div>

      {/* KPI Cards */}
      <div className="kpi-grid">
        <div className="kpi-card" title="Worst-case estimated financial loss across the entire network at the 95th percentile.">
          <span className="kpi-card__label" style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            Total Network P95 Exposure 
            <span className="material-symbols-outlined" style={{fontSize: 14, cursor: 'help'}}>info</span>
          </span>
          <div className="kpi-card__value-row">
            <span className="kpi-card__value" style={{ color: '#ff6b59' }}>{fmt(kpis?.total_network_exposure)}</span>
          </div>
        </div>
        <div className="kpi-card" title="Count of suppliers mapping to the 'Critical Priority' quadrant based on exposure and resilience.">
          <span className="kpi-card__label" style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            Critical Priority Suppliers 
            <span className="material-symbols-outlined" style={{fontSize: 14, cursor: 'help'}}>info</span>
          </span>
          <div className="kpi-card__value-row">
            <span className="kpi-card__value">{kpis?.critical_priority_count ?? '—'}</span>
            <RiskBadge quadrant="Critical" />
          </div>
        </div>
        <div className="kpi-card" title="Total budget currently allocated to high-ROI playbook interventions.">
          <span className="kpi-card__label" style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            Mitigation Budget 
            <span className="material-symbols-outlined" style={{fontSize: 14, cursor: 'help'}}>info</span>
          </span>
          <div className="kpi-card__value-row">
            <span className="kpi-card__value" style={{ color: '#ffa600' }}>{fmt(kpis?.recommended_budget)}</span>
            <span className="kpi-card__trend data-mono" style={{ color: 'var(--outline)' }}>Allocated</span>
          </div>
        </div>
        <div className="kpi-card" title="Average return on investment across all recommended mitigation actions.">
          <span className="kpi-card__label" style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            Portfolio ROI 
            <span className="material-symbols-outlined" style={{fontSize: 14, cursor: 'help'}}>info</span>
          </span>
          <div className="kpi-card__value-row">
            <span className="kpi-card__value" style={{ color: '#464c89' }}>
              {kpis?.portfolio_roi != null ? `${kpis.portfolio_roi.toFixed(2)}×` : '—'}
            </span>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="dashboard-main">
        {/* Supplier Risk Register */}
        <div className="card card--p">
          <div className="section-header">
            <h3>Supplier Risk Register</h3>
            <button className="section-header__btn" onClick={() => navigate('/suppliers')}>View All</button>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Supplier Name</th>
                  <th>Country</th>
                  <th>Tier</th>
                  <th>Risk Band</th>
                  <th>Resilience</th>
                  <th>P95 Exposure</th>
                </tr>
              </thead>
              <tbody>
                {topSuppliers.map(s => {
                  const color = bandColor(s.risk_band);
                  return (
                    <tr 
                      key={s.supplier_id} 
                      onClick={() => navigate(`/suppliers/${s.supplier_id}`)}
                      style={{ cursor: 'pointer', transition: 'background 0.2s' }}
                      onMouseEnter={e => e.currentTarget.style.background = 'var(--surface-container)'}
                      onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                      title="Click to view full supplier profile →"
                    >
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <strong style={{ color: 'var(--on-surface)' }}>{s.supplier_name}</strong>
                          <span className="material-symbols-outlined hover-arrow" style={{ fontSize: 16, color: 'var(--primary)', opacity: 0.5 }}>arrow_forward</span>
                        </div>
                      </td>
                      <td className="data-mono" style={{ color: 'var(--on-surface-variant)' }}>{s.country}</td>
                      <td style={{ color: 'var(--on-surface-variant)' }}>{s.tier ?? '—'}</td>
                      <td>{s.risk_band ? <RiskBadge riskBand={s.risk_band} /> : '—'}</td>
                      <td><ResilienceBar score={s.composite_score} color={color} /></td>
                      <td className="data-mono" style={{ color }}>{fmt(s.total_p95_exposure)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Priority Matrix */}
        <div className="card card--p">
          <div className="section-header">
            <h3>Risk Priority Matrix</h3>
            <span className="material-symbols-outlined" style={{ color: 'var(--outline-variant)' }}>more_horiz</span>
          </div>
          <div className="matrix-container">
            <div className="matrix-quadrants">
              <div className="matrix-quadrant" style={{ borderBottom: '1px solid rgba(64,71,81,0.4)', borderRight: '1px solid rgba(64,71,81,0.4)', background: 'rgba(70,76,137,0.05)' }}>
                <span className="matrix-quadrant__label label-caps" style={{ color: '#464c89', top: 8, left: 8 }}>Monitor Closely</span>
              </div>
              <div className="matrix-quadrant" style={{ borderBottom: '1px solid rgba(64,71,81,0.4)', background: 'rgba(255,107,89,0.08)' }}>
                <span className="matrix-quadrant__label label-caps" style={{ color: '#ff6b59', top: 8, right: 8 }}>Critical Priority</span>
              </div>
              <div className="matrix-quadrant" style={{ borderRight: '1px solid rgba(64,71,81,0.4)', background: 'rgba(0,61,92,0.05)' }}>
                <span className="matrix-quadrant__label label-caps" style={{ color: '#4299e1', bottom: 8, left: 8 }}>Routine Review</span>
              </div>
              <div className="matrix-quadrant" style={{ background: 'rgba(255,166,0,0.05)' }}>
                <span className="matrix-quadrant__label label-caps" style={{ color: '#ffa600', bottom: 8, right: 8 }}>Contingency</span>
              </div>
            </div>

            {/* Scatter dots */}
            {matrix.map(r => {
              const x = Math.min(95, Math.max(2, (r.total_p95_exposure / maxExp) * 96));
              const y = Math.min(95, Math.max(2, (1 - (r.resilience_score || 0)) * 96));
              const qColor = r.priority_quadrant?.toLowerCase().includes('critical') ? '#ff6b59'
                : r.priority_quadrant?.toLowerCase().includes('monitor') ? '#ffa600'
                : r.priority_quadrant?.toLowerCase().includes('contingency') ? '#ffa600'
                : '#464c89';
              const sz = 8 + (r.total_p95_exposure / maxExp) * 16;
              return (
                <div
                  key={r.supplier_id}
                  className="matrix-dot"
                  title={`${r.supplier_name || r.supplier_id}\n${r.priority_quadrant}`}
                  style={{
                    left: `${x}%`, top: `${y}%`,
                    width: sz, height: sz,
                    background: qColor,
                    boxShadow: qColor === '#ff6b59' ? `0 0 8px rgba(255,107,89,0.4)` : 'none',
                    transform: 'translate(-50%, -50%)',
                  }}
                  onClick={() => navigate(`/suppliers/${r.supplier_id}`)}
                />
              );
            })}

            <span className="matrix-axis-x">Total P95 Exposure →</span>
            <span className="matrix-axis-y">Resilience Score →</span>
          </div>
        </div>

        {/* Bottom row */}
        <div style={{ gridColumn: '1 / -1', display: 'flex', gap: 24, flexWrap: 'wrap', marginTop: 12 }}>
          
          {/* Network Resilience Before/After */}
          <div className="card card--p" style={{ flex: '1 1 300px', display: 'flex', flexDirection: 'column' }}>
            <div className="section-header">
              <h3>Systemic Resilience Projection</h3>
              <span className="material-symbols-outlined" style={{ color: 'var(--outline-variant)' }}>trending_up</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 20, marginTop: 12, flex: 1, justifyContent: 'center' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0 8px' }}>
                <div>
                  <div className="label-caps" style={{ color: 'var(--on-surface-variant)', fontSize: 10 }}>Before Mitigation</div>
                  <div className="display-sm" style={{ fontWeight: 700, margin: '4px 0', fontSize: 24 }}>
                    {kpis?.network_resilience_before != null ? (kpis.network_resilience_before * 100).toFixed(1) + '%' : '—'}
                  </div>
                </div>
                <span className="material-symbols-outlined" style={{ fontSize: 28, color: 'var(--outline-variant)' }}>arrow_forward</span>
                <div style={{ textAlign: 'right' }}>
                  <div className="label-caps" style={{ color: 'var(--primary)', fontSize: 10 }}>Projected After</div>
                  <div className="display-sm" style={{ fontWeight: 700, color: 'var(--primary)', margin: '4px 0', fontSize: 24 }}>
                    {kpis?.network_resilience_after != null ? (kpis.network_resilience_after * 100).toFixed(1) + '%' : '—'}
                  </div>
                </div>
              </div>
              
              {/* Before vs After Bar */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
                  <span style={{ color: 'var(--on-surface-variant)' }}>System Resilience Improvement</span>
                  <strong style={{ color: 'var(--primary)' }}>
                    +{kpis?.network_resilience_before != null && kpis?.network_resilience_after != null ? 
                      ((kpis.network_resilience_after - kpis.network_resilience_before) * 100).toFixed(1) + '%' : '—'}
                  </strong>
                </div>
                <div style={{ background: 'var(--surface-container-high)', height: 12, borderRadius: 6, overflow: 'hidden', display: 'flex' }}>
                  <div style={{ 
                    background: 'var(--outline)', 
                    width: `${(kpis?.network_resilience_before || 0) * 100}%`, 
                    height: '100%' 
                  }} />
                  <div style={{ 
                    background: 'var(--primary)', 
                    width: `${((kpis?.network_resilience_after || 0) - (kpis?.network_resilience_before || 0)) * 100}%`, 
                    height: '100%' 
                  }} />
                </div>
                <p className="body-xs" style={{ color: 'var(--on-surface-variant)', fontStyle: 'italic', marginTop: 4, lineHeight: 1.4 }}>
                  Target resilience assumes onboarding dual sources and deploying safety stock buffer plans.
                </p>
              </div>
            </div>
          </div>

          {/* Top 3 Actions Right Now */}
          <div className="card card--p" style={{ flex: '2 1 500px' }}>
            <div className="section-header" style={{ marginBottom: 16 }}>
              <h3>Top 3 Actions Right Now</h3>
              <button
                className="section-header__btn"
                onClick={() => navigate('/playbook')}
              >View Full Playbook</button>
            </div>
            <p className="body-xs" style={{ color: 'var(--on-surface-variant)', marginBottom: 20 }}>
              Highest-ROI mitigation actions across your critical supplier portfolio, ranked by return on investment.
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {top3Actions.map((action, i) => {
                const roiColor = action.roi >= 3 ? 'var(--primary)' : action.roi >= 1 ? '#ffa600' : '#ff6b59';
                const icon = getActionIcon(action.recommended_action);
                const priorityColors = {
                  'Critical Priority': { bg: 'rgba(255,107,89,0.08)', border: 'rgba(255,107,89,0.25)', accent: '#ff6b59' },
                  'Monitor Closely':   { bg: 'rgba(255,166,0,0.08)',  border: 'rgba(255,166,0,0.25)',  accent: '#ffa600' },
                };
                const pStyle = priorityColors[action.priority_quadrant] || { bg: 'var(--surface-container-high)', border: 'var(--outline-variant)', accent: '#464c89' };
                return (
                  <div
                    key={i}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 16,
                      background: pStyle.bg,
                      border: `1px solid ${pStyle.border}`,
                      borderRadius: 8,
                      padding: '12px 16px',
                    }}
                  >
                    {/* Rank badge */}
                    <div style={{
                      width: 28, height: 28, borderRadius: '50%',
                      background: pStyle.accent,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontWeight: 800, fontSize: 13, color: 'white', flexShrink: 0,
                    }}>
                      {i + 1}
                    </div>

                    {/* Icon */}
                    <span className="material-symbols-outlined" style={{ fontSize: 22, color: pStyle.accent, flexShrink: 0 }}>
                      {icon}
                    </span>

                    {/* Main text */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--on-surface)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {action.recommended_action} — <span style={{ color: 'var(--on-surface-variant)', fontWeight: 400 }}>{action.supplier_name}</span>
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--on-surface-variant)', marginTop: 3 }}>
                        Cost: <strong style={{ color: 'var(--on-surface)' }}>{fmt(action.action_cost ?? action.estimated_cost)}</strong>
                        &nbsp;·&nbsp;Saves: <strong style={{ color: 'var(--primary)' }}>{fmt(action.risk_reduction ?? action.p95_impact)}</strong>
                      </div>
                    </div>

                    {/* ROI badge */}
                    <div style={{
                      background: 'var(--surface-container-high)',
                      border: `1px solid ${roiColor}`,
                      borderRadius: 6, padding: '4px 10px',
                      textAlign: 'center', flexShrink: 0,
                    }}>
                      <div style={{ fontSize: 15, fontWeight: 800, color: roiColor }}>{action.roi.toFixed(1)}×</div>
                      <div style={{ fontSize: 9, color: 'var(--on-surface-variant)', letterSpacing: '0.06em', textTransform: 'uppercase' }}>ROI</div>
                    </div>
                  </div>
                );
              })}
              {top3Actions.length === 0 && (
                <div style={{ color: 'var(--on-surface-variant)', textAlign: 'center', padding: '24px 0', fontSize: 13 }}>
                  No high-ROI actions available at this time. Adjust risk thresholds or run new scenarios to generate recommendations.
                </div>
              )}
            </div>
          </div>

        </div>
      </div>
    </>
  );
}
