import React, { useState } from 'react';
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
  const [error, setError] = useState(null);

  const handleSimulate = async () => {
    setSimulating(true);
    setError(null);
    try {
      const data = await api.simulation(selectedScenario);
      setSimulatedData(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setSimulating(false);
    }
  };

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
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24 }}>
        <h2 className="headline-lg">Monte Carlo Disruption Simulator</h2>
        <p className="body-sm" style={{ color: 'var(--on-surface-variant)' }}>
          Configure a disruption vector and run 10,000 physical simulation trials per supplier.
        </p>
      </div>

      {/* Selector & Simulate Button Panel */}
      <div className="card card--p" style={{ marginBottom: 24, background: 'var(--surface-container-high)' }}>
        <h3 className="title-md" style={{ marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
          <span className="material-symbols-outlined" style={{ color: 'var(--primary)' }}>settings_input_component</span>
          Simulation Configuration
        </h3>
        <div style={{ display: 'flex', gap: 16, alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <div style={{ flex: '1 1 300px' }}>
            <label className="label-caps" style={{ color: 'var(--on-surface-variant)', display: 'block', marginBottom: 8 }}>Select Disruption Vector</label>
            <select
              value={selectedScenario}
              onChange={e => {
                setSelectedScenario(e.target.value);
                setSimulatedData(null); // Clear previous simulation results
              }}
              style={{
                width: '100%',
                background: 'var(--surface-container)',
                border: '1px solid var(--outline-variant)',
                color: 'var(--on-surface)',
                borderRadius: 6,
                padding: '12px 16px',
                fontSize: 15,
                outline: 'none',
                cursor: 'pointer'
              }}
            >
              {SCENARIOS.map(s => (
                <option key={s.id} value={s.id}>{s.label}</option>
              ))}
            </select>
          </div>
          <button
            onClick={handleSimulate}
            disabled={simulating}
            style={{
              background: 'var(--primary)',
              color: 'var(--on-primary)',
              border: 'none',
              borderRadius: 6,
              padding: '12px 28px',
              fontSize: 15,
              fontWeight: 700,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              transition: 'all 0.2s',
              opacity: simulating ? 0.7 : 1,
              boxShadow: '0 4px 12px rgba(70, 76, 137, 0.2)'
            }}
          >
            <span className="material-symbols-outlined">{simulating ? 'autorenew' : 'play_arrow'}</span>
            {simulating ? 'Simulating...' : 'Run Simulation'}
          </button>
        </div>
        {activeScenarioObj && (
          <p className="body-xs" style={{ color: 'var(--on-surface-variant)', marginTop: 12, fontStyle: 'italic' }}>
            <strong>Vector Description:</strong> {activeScenarioObj.desc}
          </p>
        )}
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

          {/* Detailed Statistics Table */}
          <div className="card card--p">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--outline-variant)', paddingBottom: 16, marginBottom: 16 }}>
              <h3 className="title-md">Monte Carlo Distribution Metrics (All Suppliers)</h3>
              <span className="material-symbols-outlined" style={{ color: 'var(--outline-variant)' }}>analytics</span>
            </div>
            <div style={{ overflowX: 'auto' }}>
              <table className="data-table" style={{ minWidth: 800 }}>
                <thead>
                  <tr>
                    <th>Supplier Name</th>
                    <th style={{ textAlign: 'right' }}>Mean Impact</th>
                    <th style={{ textAlign: 'right' }}>Std Deviation</th>
                    <th style={{ textAlign: 'right' }}>P50 (Median)</th>
                    <th style={{ textAlign: 'right' }}>P95 (Value at Risk)</th>
                    <th style={{ textAlign: 'right' }}>Zero-Impact %</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedRows.map(r => (
                    <tr key={r.supplier_id}>
                      <td><strong>{r.supplier_name}</strong></td>
                      <td className="data-mono" style={{ textAlign: 'right', color: 'var(--on-surface)' }}>{fmt(r.mean_impact)}</td>
                      <td className="data-mono" style={{ textAlign: 'right', color: 'var(--on-surface-variant)' }}>{fmt(r.std_impact)}</td>
                      <td className="data-mono" style={{ textAlign: 'right', color: 'var(--primary)' }}>{fmt(r.p50_impact)}</td>
                      <td className="data-mono" style={{ textAlign: 'right', color: '#ff6b59', fontWeight: 600 }}>{fmt(r.p95_impact)}</td>
                      <td className="data-mono" style={{ textAlign: 'right', color: 'var(--on-surface-variant)' }}>
                        {r.zero_impact_fraction != null ? `${(r.zero_impact_fraction * 100).toFixed(1)}%` : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {!simulating && !simulatedData && (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '100px 0', border: '2px dashed var(--outline-variant)', borderRadius: 8 }}>
          <span className="material-symbols-outlined" style={{ fontSize: 64, color: 'var(--outline)', marginBottom: 16 }}>model_training</span>
          <h3 className="title-lg" style={{ color: 'var(--on-surface)', marginBottom: 8 }}>No Active Simulation</h3>
          <p className="body-md" style={{ color: 'var(--on-surface-variant)', textAlign: 'center', maxWidth: 400 }}>
            Select a disruption vector above and click <strong>"Run Simulation"</strong> to execute the Monte Carlo risk analysis engine.
          </p>
        </div>
      )}
    </>
  );
}
