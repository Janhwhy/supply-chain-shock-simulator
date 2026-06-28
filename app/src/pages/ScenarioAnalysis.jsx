import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { LoadingSpinner, ErrorBox } from '../components/LoadingSpinner';

const SCENARIOS = [
  { id: 'port_strike',       label: 'Port Strike',       icon: 'anchor', desc: 'Sudden port closure disrupting maritime freight for geographically exposed suppliers' },
  { id: 'factory_shutdown',  label: 'Factory Shutdown',  icon: 'factory', desc: 'Supplier-specific production halt driven by operational failure' },
  { id: 'currency_shock',    label: 'Currency Shock',    icon: 'currency_exchange', desc: 'Macroeconomic currency devaluation affecting all suppliers in a target zone' },
  { id: 'logistics_delay',   label: 'Logistics Delay',   icon: 'local_shipping', desc: 'Systemic transport network slowdown causing widespread delivery delays' },
  { id: 'quality_failure',   label: 'Quality Failure',   icon: 'warning', desc: 'Sudden spike in defective goods requiring supplier quarantine' },
];

export function ScenarioAnalysis() {
  const [selectedScenario, setSelectedScenario] = useState('port_strike');
  const [simulatedData, setSimulatedData] = useState(null);
  const [simulating, setSimulating] = useState(false);
  const [backgroundUpdating, setBackgroundUpdating] = useState(false);
  const [error, setError] = useState(null);
  const [countdown, setCountdown] = useState(10);
  const [expandedSeverity, setExpandedSeverity] = useState({
    severe: true,
    moderate: false,
    minimal: false
  });

  const toggleSeverity = (key) => {
    setExpandedSeverity(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const handleSimulate = async (scenarioId, showFullLoader = true) => {
    if (showFullLoader) {
      setSimulating(true);
    } else {
      setBackgroundUpdating(true);
    }
    setError(null);
    try {
      const data = await api.simulation(scenarioId);
      setSimulatedData(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setSimulating(false);
      setBackgroundUpdating(false);
    }
  };

  // Run simulation immediately on selectedScenario change
  useEffect(() => {
    handleSimulate(selectedScenario, true);
    setCountdown(10);
  }, [selectedScenario]);

  // Set up 10-second auto-simulate timer
  useEffect(() => {
    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          handleSimulate(selectedScenario, false);
          return 10;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [selectedScenario]);

  const activeScenarioObj = SCENARIOS.find(s => s.id === selectedScenario);

  function fmt(n) {
    if (n == null) return '—';
    if (Math.abs(n) >= 1e7) return `₹${(n / 1e7).toFixed(2)} Cr`;
    if (Math.abs(n) >= 1e5) return `₹${(n / 1e5).toFixed(2)} L`;
    return `₹${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
  }

  // Calculate metrics if simulated
  const sortedRows = simulatedData ? [...simulatedData].sort((a, b) => (b.p95_impact || 0) - (a.p95_impact || 0)) : [];
  const top15 = sortedRows.slice(0, 15);
  const maxP95 = top15[0]?.p95_impact || 1;

  const avgP95 = simulatedData ? simulatedData.reduce((acc, r) => acc + (r.p95_impact || 0), 0) / simulatedData.length : 0;
  const maxP95All = simulatedData ? Math.max(...simulatedData.map(r => r.p95_impact || 0)) : 0;
  const avgZeroImpact = simulatedData ? (simulatedData.reduce((acc, r) => acc + (r.zero_impact_fraction || 0), 0) / simulatedData.length) * 100 : 0;

  return (
    <>
      <style>{`
        .scenario-column-card {
          cursor: pointer;
          border: 1px solid var(--outline-variant);
          background: var(--surface-container);
          transition: all 0.2s ease-in-out;
        }
        .scenario-column-card:hover {
          border-color: var(--outline);
          transform: translateY(-2px);
          background: var(--surface-container-high);
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        }
        .scenario-column-card.active {
          border: 2px solid var(--primary) !important;
          background: var(--surface-container-high);
          box-shadow: 0 0 16px rgba(153, 203, 255, 0.15);
        }
        .live-pulse {
          display: inline-block;
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: var(--primary);
          margin-right: 6px;
          animation: live-pulse-anim 1.5s infinite ease-in-out;
        }
        @keyframes live-pulse-anim {
          0% { transform: scale(0.9); opacity: 0.6; }
          50% { transform: scale(1.2); opacity: 1; box-shadow: 0 0 8px var(--primary); }
          100% { transform: scale(0.9); opacity: 0.6; }
        }
        .progress-bar-container {
          height: 4px;
          background: var(--surface-container);
          border-radius: 2px;
          overflow: hidden;
          margin-top: 8px;
          width: 100%;
        }
        .progress-bar-fill {
          height: 100%;
          background: var(--primary);
          transition: width 1s linear;
        }
        .spin {
          animation: spin-anim 1s linear infinite;
          display: inline-block;
        }
        @keyframes spin-anim {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24 }}>
        <h2 className="headline-lg">Monte Carlo Disruption Simulator</h2>
        <p className="body-sm" style={{ color: 'var(--on-surface-variant)' }}>
          Configure a disruption vector and run 10,000 physical simulation trials per supplier.
        </p>
      </div>

      {/* Scenarios Columns Grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(5, 1fr)',
        gap: '16px',
        marginBottom: '24px'
      }}>
        {SCENARIOS.map(s => {
          const selected = s.id === selectedScenario;
          return (
            <div
              key={s.id}
              onClick={() => {
                if (selectedScenario !== s.id) {
                  setSelectedScenario(s.id);
                  setSimulatedData(null);
                }
              }}
              className={`scenario-column-card ${selected ? 'active' : ''}`}
              style={{
                display: 'flex',
                flexDirection: 'column',
                padding: '16px',
                borderRadius: '8px',
                minHeight: '180px',
                justifyContent: 'space-between',
              }}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                  <span className="material-symbols-outlined" style={{ color: selected ? 'var(--primary)' : 'var(--outline)' }}>
                    {s.icon}
                  </span>
                  <h4 style={{ fontWeight: 600, fontSize: '15px', color: selected ? 'var(--primary)' : 'var(--on-surface)' }}>
                    {s.label}
                  </h4>
                </div>
                <p style={{ fontSize: '12px', color: 'var(--on-surface-variant)', lineHeight: '1.4' }}>
                  {s.desc}
                </p>
              </div>

              <div style={{ marginTop: '12px' }}>
                {!selected && (
                  <span style={{ fontSize: '11px', color: 'var(--outline)', fontWeight: 500 }}>
                    Click to simulate
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {error && <ErrorBox message={error} />}

      {simulating && (
        <div style={{ padding: '60px 0' }}>
          <LoadingSpinner message={`Running 10,000 trials for scenario: ${activeScenarioObj?.label}…`} />
        </div>
      )}

      {/* Simulation Results Output */}
      {!simulating && simulatedData && (
        <>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <h3 className="title-md" style={{ margin: 0 }}>
                Simulation Results — <span style={{ color: 'var(--primary)' }}>{activeScenarioObj?.label}</span>
              </h3>
              {backgroundUpdating && (
                <span className="material-symbols-outlined spin" style={{ color: 'var(--primary)', fontSize: 18 }}>
                  sync
                </span>
              )}
            </div>
            <button
              onClick={() => {
                handleSimulate(selectedScenario, false);
                setCountdown(10);
              }}
              disabled={backgroundUpdating || simulating}
              style={{
                background: 'var(--surface-container-high)',
                border: '1px solid var(--outline-variant)',
                color: 'var(--on-surface)',
                borderRadius: 6,
                padding: '6px 12px',
                fontSize: 13,
                fontWeight: 600,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                transition: 'all 0.2s',
                opacity: backgroundUpdating ? 0.7 : 1
              }}
            >
              <span className={`material-symbols-outlined ${backgroundUpdating ? 'spin' : ''}`} style={{ fontSize: 16 }}>
                refresh
              </span>
              Manual Refresh
            </button>
          </div>

          {/* Simulation Summary KPIs */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 16, marginBottom: 24 }}>
            <div className="card card--p" style={{ borderLeft: '4px solid var(--primary)' }}>
              <div className="label-caps" style={{ color: 'var(--on-surface-variant)' }}>Simulation Run</div>
              <div className="title-md" style={{ margin: '8px 0', fontWeight: 700, color: 'var(--primary)', textTransform: 'uppercase' }}>
                {activeScenarioObj?.label}
              </div>
              <div className="body-xs" style={{ color: 'var(--on-surface-variant)' }}>10,000 trials completed</div>
            </div>
            <div className="card card--p" style={{ borderLeft: '4px solid #ff6b59' }}>
              <div className="label-caps" style={{ color: 'var(--on-surface-variant)' }}>Max Simulated Loss</div>
              <div className="display-sm" style={{ margin: '8px 0', fontWeight: 700, color: '#ff6b59' }}>
                {fmt(maxP95All)}
              </div>
              <div className="body-xs" style={{ color: 'var(--on-surface-variant)' }}>Peak value-at-risk exposure</div>
            </div>
            <div className="card card--p" style={{ borderLeft: '4px solid #ffa600' }}>
              <div className="label-caps" style={{ color: 'var(--on-surface-variant)' }}>Average Scenario Risk</div>
              <div className="display-sm" style={{ margin: '8px 0', fontWeight: 700 }}>
                {fmt(avgP95)}
              </div>
              <div className="body-xs" style={{ color: 'var(--on-surface-variant)' }}>Mean supplier exposure</div>
            </div>
            <div className="card card--p" style={{ borderLeft: '4px solid #8b91c7' }}>
              <div className="label-caps" style={{ color: 'var(--on-surface-variant)' }}>Zero-Impact Probability</div>
              <div className="display-sm" style={{ margin: '8px 0', fontWeight: 700 }}>
                {avgZeroImpact.toFixed(1)}%
              </div>
              <div className="body-xs" style={{ color: 'var(--on-surface-variant)' }}>Mean trials with zero financial shock</div>
            </div>
          </div>

          {/* Bar Chart */}
          <div className="card card--p" style={{ marginBottom: 24 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--outline-variant)', paddingBottom: 16, marginBottom: 16 }}>
              <h3 className="title-md">
                Supplier P95 Exposure — <span style={{ color: 'var(--primary)' }}>{activeScenarioObj?.label}</span>
              </h3>
              <span className="material-symbols-outlined" style={{ color: 'var(--outline-variant)' }}>bar_chart</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {top15.map((r, i) => {
                const pct = (r.p95_impact / maxP95) * 100;
                return (
                  <div key={r.supplier_id} style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                    <div className="data-mono" style={{ width: 180, color: 'var(--on-surface-variant)', textAlign: 'right', fontSize: 12, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                      title={r.supplier_name}>{r.supplier_name}</div>
                    <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 12 }}>
                      <div style={{ flex: 1 }}>
                        <div style={{ height: 20, background: '#464c89', borderRadius: '0 4px 4px 0', width: `${pct}%`, opacity: 0.85 + 0.15 * (1 - i / top15.length) }} />
                      </div>
                      <span className="data-mono" style={{ color: 'var(--on-surface)', whiteSpace: 'nowrap', minWidth: 80, textAlign: 'right' }}>{fmt(r.p95_impact)}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Monte Carlo Distribution Histogram */}
          <MonteCarloHistogram data={simulatedData} scenarioLabel={activeScenarioObj?.label} fmt={fmt} />

          {/* Severity Grouped Accordion */}
          <div className="card card--p">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--outline-variant)', paddingBottom: 16, marginBottom: 16 }}>
              <h3 className="title-md">Monte Carlo Distribution Metrics (All Suppliers)</h3>
              <span className="material-symbols-outlined" style={{ color: 'var(--outline-variant)' }}>analytics</span>
            </div>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {[
                { key: 'severe', label: '🔴 Severe Impact', count: sortedRows.filter(r => (r.p95_impact || 0) > 1000000).length, data: sortedRows.filter(r => (r.p95_impact || 0) > 1000000), color: '#ff6b59' },
                { key: 'moderate', label: '🟡 Moderate Impact', count: sortedRows.filter(r => (r.p95_impact || 0) > 100000 && (r.p95_impact || 0) <= 1000000).length, data: sortedRows.filter(r => (r.p95_impact || 0) > 100000 && (r.p95_impact || 0) <= 1000000), color: '#ffa600' },
                { key: 'minimal', label: '⚪ Minimal Impact', count: sortedRows.filter(r => (r.p95_impact || 0) <= 100000).length, data: sortedRows.filter(r => (r.p95_impact || 0) <= 100000), color: 'var(--on-surface-variant)' }
              ].map(group => (
                <div key={group.key} style={{ border: '1px solid var(--outline-variant)', borderRadius: 8, overflow: 'hidden' }}>
                  <div 
                    onClick={() => toggleSeverity(group.key)}
                    style={{ 
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between', 
                      padding: '12px 16px', background: 'var(--surface-container-high)', cursor: 'pointer',
                      borderBottom: expandedSeverity[group.key] ? '1px solid var(--outline-variant)' : 'none'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span className="material-symbols-outlined" style={{ fontSize: 18, color: 'var(--on-surface-variant)', transition: 'transform 0.2s', transform: expandedSeverity[group.key] ? 'rotate(90deg)' : 'rotate(0deg)' }}>chevron_right</span>
                      <strong style={{ fontSize: 14, color: 'var(--on-surface)' }}>{group.label} ({group.count} suppliers)</strong>
                    </div>
                  </div>
                  {expandedSeverity[group.key] && (
                    <div style={{ background: 'var(--surface)', padding: '0 16px' }}>
                      {group.data.length > 0 ? (
                        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                          <thead>
                            <tr>
                              <th style={{ textAlign: 'left', padding: '12px 0', borderBottom: '1px solid var(--outline-variant)', color: 'var(--on-surface-variant)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Supplier Name</th>
                              <th style={{ textAlign: 'right', padding: '12px 0', borderBottom: '1px solid var(--outline-variant)', color: 'var(--on-surface-variant)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Mean Impact</th>
                              <th style={{ textAlign: 'right', padding: '12px 0', borderBottom: '1px solid var(--outline-variant)', color: 'var(--on-surface-variant)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.05em' }}>P95 (Value at Risk)</th>
                              <th style={{ textAlign: 'right', padding: '12px 0', borderBottom: '1px solid var(--outline-variant)', color: 'var(--on-surface-variant)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Zero-Impact %</th>
                            </tr>
                          </thead>
                          <tbody>
                            {group.data.map(r => (
                              <tr key={r.supplier_id}>
                                <td style={{ padding: '10px 0', borderBottom: '1px solid var(--outline-variant)' }}><strong>{r.supplier_name}</strong></td>
                                <td className="data-mono" style={{ textAlign: 'right', padding: '10px 0', borderBottom: '1px solid var(--outline-variant)', color: 'var(--on-surface)' }}>{fmt(r.mean_impact)}</td>
                                <td className="data-mono" style={{ textAlign: 'right', padding: '10px 0', borderBottom: '1px solid var(--outline-variant)', color: group.color, fontWeight: 600 }}>{fmt(r.p95_impact)}</td>
                                <td className="data-mono" style={{ textAlign: 'right', padding: '10px 0', borderBottom: '1px solid var(--outline-variant)', color: 'var(--on-surface-variant)' }}>
                                  {r.zero_impact_fraction != null ? `${(r.zero_impact_fraction * 100).toFixed(1)}%` : '—'}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      ) : (
                        <div style={{ padding: '24px', textAlign: 'center', color: 'var(--on-surface-variant)', fontSize: 13 }}>No suppliers in this category.</div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {!simulating && !simulatedData && (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '100px 0', border: '2px dashed var(--outline-variant)', borderRadius: 8 }}>
          <span className="material-symbols-outlined" style={{ fontSize: 64, color: 'var(--outline)', marginBottom: 16 }}>model_training</span>
          <h3 className="title-lg" style={{ color: 'var(--on-surface)', marginBottom: 8 }}>No Active Simulation</h3>
          <p className="body-md" style={{ color: 'var(--on-surface-variant)', textAlign: 'center', maxWidth: 400 }}>
            Select a disruption vector card above to execute the Monte Carlo risk analysis engine automatically.
          </p>
        </div>
      )}
    </>
  );
}

/** Monte Carlo distribution histogram — buckets supplier P95 values and renders bell-curve SVG */
function MonteCarloHistogram({ data, scenarioLabel, fmt }) {
  if (!data || data.length === 0) return null;

  const BINS = 20;
  const W = 560, H = 180, PAD = { top: 16, right: 24, bottom: 36, left: 52 };
  const innerW = W - PAD.left - PAD.right;
  const innerH = H - PAD.top - PAD.bottom;

  const values = data.map(r => r.p95_impact || 0).filter(v => v > 0);
  if (values.length === 0) return null;

  const minV = Math.min(...values);
  const maxV = Math.max(...values);
  const range = maxV - minV || 1;
  const binWidth = range / BINS;

  const counts = Array(BINS).fill(0);
  values.forEach(v => {
    const idx = Math.min(BINS - 1, Math.floor((v - minV) / binWidth));
    counts[idx]++;
  });
  const maxCount = Math.max(...counts, 1);

  // P50 and P95 of the cross-supplier P95 distribution
  const sorted = [...values].sort((a, b) => a - b);
  const p50 = sorted[Math.floor(sorted.length * 0.50)];
  const p95 = sorted[Math.floor(sorted.length * 0.95)];

  function xScale(v) {
    return PAD.left + ((v - minV) / range) * innerW;
  }
  function yScale(count) {
    return PAD.top + innerH - (count / maxCount) * innerH;
  }

  // Smooth curve points through bin centers
  const curvePoints = counts.map((c, i) => {
    const bx = xScale(minV + (i + 0.5) * binWidth);
    const by = yScale(c);
    return `${bx},${by}`;
  });
  const pathD = `M ${curvePoints.join(' L ')}`;

  // X-axis ticks
  const ticks = 5;
  const xTicks = Array.from({ length: ticks + 1 }, (_, i) => minV + (range / ticks) * i);

  return (
    <div className="card card--p" style={{ marginBottom: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--outline-variant)', paddingBottom: 16, marginBottom: 20 }}>
        <div>
          <h3 className="title-md">
            Monte Carlo Distribution — <span style={{ color: 'var(--primary)' }}>{scenarioLabel}</span>
          </h3>
          <p className="body-xs" style={{ color: 'var(--on-surface-variant)', marginTop: 4 }}>
            Frequency of P95 worst-case loss values across {values.length} suppliers. P50 = median exposure, P95 = portfolio tail risk threshold.
          </p>
        </div>
        <div style={{ display: 'flex', gap: 16, alignItems: 'center', flexShrink: 0 }}>
          {[['P50 Median', '#4299e1', p50], ['P95 Tail Risk', '#ff6b59', p95]].map(([label, color, val]) => (
            <div key={label} style={{ textAlign: 'right' }}>
              <div style={{ fontSize: 10, color: 'var(--on-surface-variant)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</div>
              <div style={{ fontWeight: 700, color, fontSize: 15 }}>{fmt(val)}</div>
            </div>
          ))}
        </div>
      </div>

      <div style={{ overflowX: 'auto' }}>
        <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', maxWidth: W, display: 'block', margin: '0 auto' }}>
          {/* Grid lines */}
          {[0.25, 0.5, 0.75, 1].map(frac => {
            const y = PAD.top + innerH * (1 - frac);
            return (
              <line key={frac} x1={PAD.left} y1={y} x2={W - PAD.right} y2={y}
                stroke="var(--outline-variant)" strokeWidth={0.5} strokeDasharray="3 4" />
            );
          })}

          {/* Histogram bars */}
          {counts.map((c, i) => {
            const bx = PAD.left + (i / BINS) * innerW;
            const bw = (innerW / BINS) - 1;
            const bh = (c / maxCount) * innerH;
            const by = PAD.top + innerH - bh;
            const barColor = (minV + (i + 0.5) * binWidth) >= p95 ? 'rgba(255,107,89,0.65)' : 'rgba(70,76,137,0.6)';
            return (
              <rect key={i} x={bx} y={by} width={bw} height={bh}
                fill={barColor} rx={2} />
            );
          })}

          {/* Smooth curve overlay */}
          <polyline points={curvePoints.join(' ')} fill="none"
            stroke="rgba(153,203,255,0.7)" strokeWidth={2} strokeLinejoin="round" />

          {/* P50 marker */}
          <line x1={xScale(p50)} y1={PAD.top} x2={xScale(p50)} y2={PAD.top + innerH}
            stroke="#4299e1" strokeWidth={1.5} strokeDasharray="4 3" />
          <text x={xScale(p50) + 4} y={PAD.top + 12} fill="#4299e1" fontSize={9} fontWeight={700}>P50</text>

          {/* P95 marker */}
          <line x1={xScale(p95)} y1={PAD.top} x2={xScale(p95)} y2={PAD.top + innerH}
            stroke="#ff6b59" strokeWidth={1.5} strokeDasharray="4 3" />
          <text x={xScale(p95) + 4} y={PAD.top + 12} fill="#ff6b59" fontSize={9} fontWeight={700}>P95</text>

          {/* Shaded P95 tail area */}
          {(() => {
            const x1 = xScale(p95);
            const x2 = W - PAD.right;
            return (
              <rect x={x1} y={PAD.top} width={Math.max(0, x2 - x1)} height={innerH}
                fill="rgba(255,107,89,0.06)" />
            );
          })()}

          {/* X-axis */}
          <line x1={PAD.left} y1={PAD.top + innerH} x2={W - PAD.right} y2={PAD.top + innerH}
            stroke="var(--outline-variant)" strokeWidth={1} />
          {xTicks.map((v, i) => (
            <g key={i}>
              <line x1={xScale(v)} y1={PAD.top + innerH} x2={xScale(v)} y2={PAD.top + innerH + 4}
                stroke="var(--outline-variant)" strokeWidth={1} />
              <text x={xScale(v)} y={PAD.top + innerH + 14} textAnchor="middle"
                fill="var(--on-surface-variant)" fontSize={8.5}>
                {fmt(v)}
              </text>
            </g>
          ))}

          {/* Y-axis label */}
          <text x={14} y={PAD.top + innerH / 2} textAnchor="middle"
            fill="var(--on-surface-variant)" fontSize={9}
            transform={`rotate(-90, 14, ${PAD.top + innerH / 2})`}>
            # Suppliers
          </text>

          {/* X-axis label */}
          <text x={W / 2} y={H - 4} textAnchor="middle"
            fill="var(--on-surface-variant)" fontSize={9}>
            Worst-Case Loss (P95) →
          </text>
        </svg>
      </div>
    </div>
  );
}
