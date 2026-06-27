import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { ResilienceGauge } from '../components/ResilienceGauge';
import { RiskBadge } from '../components/RiskBadge';
import { LoadingSpinner, ErrorBox } from '../components/LoadingSpinner';

function fmt(n, unit = '₹') {
  if (n == null) return '—';
  if (Math.abs(n) >= 1e7) return `${unit}${(n / 1e7).toFixed(1)} Cr`;
  if (Math.abs(n) >= 1e5) return `${unit}${(n / 1e5).toFixed(1)} L`;
  return `${unit}${n.toFixed(0)}`;
}

const SCENARIO_NAMES = {
  port_strike: 'Port Strike',
  factory_shutdown: 'Factory Shutdown',
  currency_shock: 'Currency Shock',
  logistics_delay: 'Logistics Delay',
  quality_failure: 'Quality Failure',
};

const GAUGE_DEFS = [
  { key: 'dependency_risk',      label: 'Dependency Risk',      color: '#ff6b59' },
  { key: 'geo_risk',             label: 'Geographic Risk',      color: '#ffa600' },
  { key: 'reliability_risk',     label: 'Reliability Risk',     color: '#954e9b' },
  { key: 'substitutability_risk',label: 'Substitutability Risk',color: '#ff6b59' },
];

export function SupplierDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.supplier(id)
      .then(d => { setData(d); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });
  }, [id]);

  if (loading) return <LoadingSpinner message="Loading supplier detail…" />;
  if (error)   return <ErrorBox message={error} />;

  const scores = data.resilience_scores?.[0] || {};
  const pm = data.priority_matrix?.[0] || {};
  const simResults = data.simulation_results || [];
  const playbook = data.playbook?.[0] || null;
  const scoreInterp = data.score_interpretation || {};

  // Max sim value for bar height scaling
  const maxSim = Math.max(...simResults.map(r => r.p95_impact || 0), 1);

  return (
    <>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', paddingBottom: 24, borderBottom: '1px solid var(--outline-variant)', marginBottom: 24 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
            <button onClick={() => navigate(-1)} style={{ color: 'var(--on-surface-variant)', display: 'flex', alignItems: 'center', gap: 4 }}>
              <span className="material-symbols-outlined">arrow_back</span>
            </button>
            <span className="display-lg" style={{ fontSize: 36 }}>{data.supplier_name}</span>
            <span className="title-md" style={{ color: 'var(--on-surface-variant)' }}>{data.country}</span>
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ padding: '2px 8px', borderRadius: 4, border: '1px solid var(--outline-variant)', background: 'var(--surface-container)', fontSize: 12, fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase' }}>
              Tier {data.tier ?? '—'} Supplier
            </span>
            {pm.priority_quadrant && <RiskBadge quadrant={pm.priority_quadrant} />}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 12 }}>
          <button
            onClick={() => {
              const rows = [['field','value']];
              Object.entries(data).forEach(([k,v]) => { if (typeof v !== 'object') rows.push([k, v]); });
              const csv = rows.map(r => r.join(',')).join('\n');
              const a = document.createElement('a'); a.href = 'data:text/csv;charset=utf-8,' + encodeURIComponent(csv); a.download = `supplier_${id}.csv`; a.click();
            }}
            style={{ padding: '8px 24px', borderRadius: 4, border: '1px solid #003d5c', color: '#003d5c', fontSize: 14, fontWeight: 600, transition: 'all 0.2s' }}
          >Export Report</button>
          <button
            onClick={() => window.open(`mailto:contact@${data.supplier_name?.toLowerCase().replace(/[^a-z0-9]/g, '')}.com?subject=Risk%20Mitigation%20Discussion`)}
            style={{ padding: '8px 24px', borderRadius: 4, background: '#464c89', color: 'white', fontSize: 14, fontWeight: 600 }}
          >Contact Lead</button>
        </div>
      </div>

      {/* Score Interpretation Card */}
      {scoreInterp.risk_band && (
        <div className="card card--p" style={{ marginBottom: 24, borderLeft: `6px solid ${scoreInterp.urgency_level === 'Immediate' ? '#ff6b59' : '#ffa600'}`, background: 'var(--surface-container-high)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <h3 className="title-md" style={{ color: 'var(--on-surface)' }}>Systemic Risk Interpretation</h3>
            <span style={{ 
              background: scoreInterp.urgency_level === 'Immediate' ? 'rgba(255, 107, 89, 0.15)' : 'rgba(255, 166, 0, 0.15)',
              color: scoreInterp.urgency_level === 'Immediate' ? '#ff6b59' : '#ffa600',
              padding: '4px 12px',
              borderRadius: 100,
              fontSize: 12,
              fontWeight: 700,
              textTransform: 'uppercase',
              letterSpacing: '0.05em'
            }}>
              Urgency: {scoreInterp.urgency_level}
            </span>
          </div>
          <p className="body-md" style={{ color: 'var(--on-surface)', marginBottom: 8, fontSize: 15, fontWeight: 500 }}>
            {scoreInterp.interpretation}
          </p>
          <div className="body-sm" style={{ color: 'var(--on-surface-variant)', display: 'flex', gap: 6, alignItems: 'center' }}>
            <span className="material-symbols-outlined" style={{ fontSize: 18, color: 'var(--primary)' }}>info</span>
            <span><strong>Mitigation Strategy:</strong> {scoreInterp.recommended_action}</span>
          </div>
        </div>
      )}

      {/* Risk Gauges */}
      <div className="gauges-grid" style={{ marginBottom: 24 }}>
        {GAUGE_DEFS.map(({ key, label, color }) => (
          <ResilienceGauge key={key} label={label} value={scores[key]} color={color} />
        ))}
      </div>

      {/* Simulation Chart + Recommended Action */}
      <div className="detail-grid">
        {/* Simulation Results */}
        <div className="card card--p">
          <h3 className="title-md" style={{ marginBottom: 16 }}>Simulation Results — Median vs Worst-Case Loss</h3>
          <div className="sim-chart">
            {simResults.map((r, i) => {
              const name = Object.values(SCENARIO_NAMES).find(n => r.scenario_name?.includes(n.split(' ')[0])) || r.scenario_name;
              const p50h = (r.p50_impact / maxSim) * 100;
              const p95h = (r.p95_impact / maxSim) * 100;
              return (
                <div key={i} className="sim-bar-group">
                  <div className="sim-bar-pair">
                    <div className="sim-bar" style={{ height: `${p50h}%`, background: '#464c89', opacity: 0.85 }} title={`Median Loss: ${fmt(r.p50_impact)}`} />
                    <div className="sim-bar" style={{ height: `${p95h}%`, background: '#ff6b59' }} title={`Worst-Case Loss: ${fmt(r.p95_impact)}`} />
                  </div>
                  <span className="sim-label">{r.scenario_name?.split(' ').slice(0, 2).join(' ') || `S${i+1}`}</span>
                </div>
              );
            })}
          </div>
          <div style={{ display: 'flex', justifyContent: 'center', gap: 24, marginTop: 8 }}>
            {[['#464c89','Median Loss'],['#ff6b59','Worst-Case Loss']].map(([color, label]) => (
              <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <div style={{ width: 12, height: 12, background: color, borderRadius: 2, opacity: color === '#464c89' ? 0.85 : 1 }} />
                <span className="data-mono" style={{ color: 'var(--on-surface-variant)' }}>{label}</span>
              </div>
            ))}
          </div>

          {/* Detailed Stats Table */}
          <div style={{ marginTop: 24, borderTop: '1px solid var(--outline-variant)', paddingTop: 16 }}>
            <h4 className="title-sm" style={{ marginBottom: 12, color: 'var(--on-surface)' }}>Distribution Parameters</h4>
            <div style={{ overflowX: 'auto' }}>
              <table className="data-table" style={{ width: '100%', fontSize: 13 }}>
                <thead>
                  <tr>
                    <th>Scenario</th>
                    <th style={{ textAlign: 'right' }}>Mean Impact</th>
                    <th style={{ textAlign: 'right' }}>Std Dev</th>
                    <th style={{ textAlign: 'right' }}>Skewness</th>
                    <th style={{ textAlign: 'right' }}>Volatility Ratio</th>
                  </tr>
                </thead>
                <tbody>
                  {simResults.map((r, i) => (
                    <tr key={i}>
                      <td><strong>{SCENARIO_NAMES[r.scenario_name] || r.scenario_name}</strong></td>
                      <td className="data-mono" style={{ textAlign: 'right', color: 'var(--on-surface)' }}>{fmt(r.mean_impact)}</td>
                      <td className="data-mono" style={{ textAlign: 'right', color: 'var(--on-surface-variant)' }}>{fmt(r.std_impact)}</td>
                      <td className="data-mono" style={{ textAlign: 'right', color: r.skewness > 1.5 ? '#ff6b59' : 'var(--on-surface)' }}>{r.skewness != null ? r.skewness.toFixed(2) : '—'}</td>
                      <td className="data-mono" style={{ textAlign: 'right' }}>{r.var_ratio != null ? `${r.var_ratio.toFixed(2)}x` : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Recommended Action Card */}
        <div className="card card--p" style={{ position: 'relative', overflow: 'hidden' }}>
          <div style={{ position: 'absolute', top: 0, right: 0, width: 128, height: 128, background: 'rgba(149,78,155,0.08)', borderRadius: '50%', filter: 'blur(32px)', transform: 'translate(50%, -50%)', pointerEvents: 'none' }} />
          {playbook ? (
            <div className="action-card">
              <div>
                <h3 className="title-md" style={{ marginBottom: 4 }}>Recommended Action</h3>
                <p className="headline-lg-mobile" style={{ color: '#954e9b', marginBottom: 16 }}>{playbook.recommended_action}</p>
                <div>
                  {[
                    ['Scenario', playbook.scenario],
                    ['Estimated Cost', fmt(playbook.estimated_cost)],
                    ['Worst-Case Loss', fmt(playbook.p95_impact)],
                    ['ROI', `${(playbook.roi || 0).toFixed(2)}×`],
                  ].map(([label, value]) => (
                    <div key={label} className="action-card__row">
                      <span className="body-sm" style={{ color: 'var(--on-surface-variant)' }}>{label}</span>
                      <span className="data-mono">{value}</span>
                    </div>
                  ))}
                </div>
              </div>
              <button
                onClick={() => navigate('/playbook')}
                style={{ width: '100%', padding: '8px 0', borderRadius: 4, border: '1px solid #003d5c', color: '#003d5c', fontSize: 14, fontWeight: 600, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, marginTop: 16, transition: 'all 0.2s' }}
              >
                View Full Playbook
                <span className="material-symbols-outlined" style={{ fontSize: 20 }}>arrow_forward</span>
              </button>
            </div>
          ) : (
            <div style={{ color: 'var(--on-surface-variant)', fontSize: 14, textAlign: 'center', padding: '40px 0' }}>
              No playbook entry for this supplier. Consider generating a custom mitigation plan if they are mission-critical.
            </div>
          )}
        </div>
      </div>

      {/* Additional metrics */}
      {data.reliability_score != null && (
        <div className="card card--p" style={{ marginTop: 24 }}>
          <h3 className="title-md" style={{ marginBottom: 16 }}>Operational Metrics</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
            {[
              ['Reliability Score', data.reliability_score?.toFixed(3)],
              ['Avg Delay Days', data.avg_delay_days?.toFixed(1)],
              ['Delay Volatility', data.delay_volatility?.toFixed(3)],
              ['Rejection Rate', data.rejection_rate != null ? `${(data.rejection_rate * 100).toFixed(1)}%` : '—'],
            ].map(([label, value]) => (
              <div key={label} style={{ background: 'var(--surface-container-high)', borderRadius: 4, padding: 16 }}>
                <div className="label-caps" style={{ color: 'var(--on-surface-variant)', marginBottom: 8 }}>{label}</div>
                <div className="data-mono" style={{ fontSize: 20, color: 'var(--on-surface)' }}>{value ?? '—'}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
