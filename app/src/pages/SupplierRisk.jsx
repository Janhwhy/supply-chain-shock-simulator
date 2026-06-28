import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { RiskBadge } from '../components/RiskBadge';
import { LoadingSpinner, ErrorBox } from '../components/LoadingSpinner';
import { Treemap, Tooltip, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, PieChart, Pie, Cell, LabelList } from 'recharts';


function bandColor(band) {
  if (!band) return '#8a919c';
  const b = band.toLowerCase();
  if (b === 'critical') return '#ff6b59';
  if (b === 'high')     return '#ffa600';
  if (b === 'medium')   return '#8b91c7';
  return '#4299e1';
}

export function SupplierRisk() {
  const navigate = useNavigate();
  const [suppliers, setSuppliers] = useState([]);
  const [relationships, setRelationships] = useState([]);
  const [filtered, setFiltered] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState('');
  const [bandFilter, setBandFilter] = useState('');
  const [sortKey, setSortKey] = useState('total_p95_exposure');
  const [sortDir, setSortDir] = useState(-1);

  const [activeView, setActiveView] = useState('Table');
  const [chartCountryFilter, setChartCountryFilter] = useState('');
  const [chartTierFilter, setChartTierFilter] = useState('');
  const [chartBandFilter, setChartBandFilter] = useState('');
  
  const [collapsedGroups, setCollapsedGroups] = useState({
    'Critical Priority': false,
    'Monitor Closely': false,
    'Contingency Plan': true,
    'Routine Review': true,
  });

  const toggleGroup = (grp) => {
    setCollapsedGroups(prev => ({ ...prev, [grp]: !prev[grp] }));
  };


  useEffect(() => {
    Promise.all([api.suppliers(), api.relationships()])
      .then(([s, r]) => { setSuppliers(s); setRelationships(r); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });
  }, []);

  // Build single-source map: supplier_id -> true if any product they supply is sole-sourced
  const singleSourceSupplierIds = new Set();
  if (relationships.length > 0) {
    const productSupplierCount = {};
    relationships.forEach(r => {
      if (!productSupplierCount[r.product_id]) productSupplierCount[r.product_id] = new Set();
      productSupplierCount[r.product_id].add(r.supplier_id);
    });
    Object.entries(productSupplierCount).forEach(([, supSet]) => {
      if (supSet.size === 1) {
        supSet.forEach(sid => singleSourceSupplierIds.add(sid));
      }
    });
  }

  useEffect(() => {
    let data = [...suppliers];
    if (search) data = data.filter(s => s.supplier_name?.toLowerCase().includes(search.toLowerCase()) || s.country?.toLowerCase().includes(search.toLowerCase()));
    if (bandFilter) data = data.filter(s => s.risk_band?.toLowerCase() === bandFilter.toLowerCase());
    
    if (chartCountryFilter) data = data.filter(s => s.country === chartCountryFilter);
    if (chartTierFilter) data = data.filter(s => String(s.tier) === chartTierFilter);
    if (chartBandFilter) data = data.filter(s => s.risk_band === chartBandFilter);
    data.sort((a, b) => sortDir * ((a[sortKey] || 0) - (b[sortKey] || 0)));
    setFiltered(data);
  }, [suppliers, search, bandFilter, sortKey, sortDir, chartCountryFilter, chartTierFilter, chartBandFilter]);

  function toggleSort(key) {
    if (sortKey === key) setSortDir(d => -d);
    else { setSortKey(key); setSortDir(-1); }
  }

  if (loading) return <LoadingSpinner message="Loading supplier data…" />;
  if (error)   return <ErrorBox message={error} />;

  
  // Insight computations
  const maxP95Supplier = [...suppliers].sort((a, b) => (b.total_p95_exposure || 0) - (a.total_p95_exposure || 0))[0];
  const criticalCount = suppliers.filter(s => s.priority_quadrant === 'Critical Priority').length;
  const criticalSuppliers = suppliers.filter(s => s.priority_quadrant === 'Critical Priority');
  const countryCounts = {};
  criticalSuppliers.forEach(s => {
    if (s.country) countryCounts[s.country] = (countryCounts[s.country] || 0) + 1;
  });
  const mostFreqCountry = Object.entries(countryCounts).sort((a, b) => b[1] - a[1])[0]?.[0] || 'N/A';
  const lowResilienceCount = suppliers.filter(s => s.resilience_score != null && s.resilience_score < 0.20).length;

  const InsightCard = ({ title, value }) => (
    <div style={{ background: 'var(--component-bg-focus)', borderLeft: '3px solid #dd4d88', borderRadius: 8, padding: 12, flex: 1 }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--on-surface-variant)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{title}</div>
      <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--on-surface)' }}>{value}</div>
    </div>
  );

  function fmt(n) {
    if (n == null) return '—';
    if (Math.abs(n) >= 1e7) return `₹${(n / 1e7).toFixed(1)} Cr`;
    if (Math.abs(n) >= 1e5) return `₹${(n / 1e5).toFixed(1)} L`;
    return n.toFixed(2);
  }

  // Risk distribution counts
  const BANDS = ['Critical', 'High', 'Medium', 'Low'];

  // Compute chart data from unfiltered `suppliers`
  const countryDist = {};
  suppliers.forEach(s => { if (s.country) countryDist[s.country] = (countryDist[s.country] || 0) + 1; });
  const countryChartData = Object.entries(countryDist).sort((a, b) => b[1] - a[1]).slice(0, 8).map(([name, value]) => ({ name, value }));

  const tierDist = {};
  suppliers.forEach(s => { if (s.tier != null) tierDist[s.tier] = (tierDist[s.tier] || 0) + 1; });
  const tierChartData = Object.entries(tierDist).map(([name, value]) => ({ name: String(name), value }));
  const tierColors = ['#8b91c7', '#4299e1', '#464c89', '#99cbff'];

  const riskBandOrder = { 'Critical': 1, 'High': 2, 'Medium': 3, 'Low': 4 };
  const riskBandColors = { 'Critical': '#dd4d88', 'High': '#ff6b59', 'Medium': '#ffa600', 'Low': '#38A169' };
  const bandDist = {};
  suppliers.forEach(s => { if (s.risk_band) bandDist[s.risk_band] = (bandDist[s.risk_band] || 0) + 1; });
  const bandChartData = Object.entries(bandDist).sort((a, b) => riskBandOrder[a[0]] - riskBandOrder[b[0]]).map(([name, value]) => ({ name, value }));

  const bandCounts = {};
  BANDS.forEach(b => { bandCounts[b] = suppliers.filter(s => s.risk_band === b).length; });
  const total = suppliers.length || 1;

  return (
    <>
      <style>{`
        .treemap-cell rect {
          transition: all 0.2s ease;
        }
        .treemap-cell:hover rect {
          filter: brightness(1.2) drop-shadow(0 4px 6px rgba(0,0,0,0.3));
          stroke: #fff !important;
          stroke-width: 2px !important;
        }
        .treemap-text {
          pointer-events: none;
          font-family: 'Inter', system-ui, sans-serif;
          fill: var(--text-inverse);
          font-weight: 600;
          text-shadow: 0 1px 3px rgba(0,0,0,0.8);
        }
      `}</style>
      <div className="page-header">
        <div>
          <h2 className="headline-lg">Supplier Risk Register</h2>
          <p className="body-sm" style={{ color: 'var(--on-surface-variant)', marginTop: 4 }}>
            {total} suppliers ranked by financial exposure and resilience score.
            &nbsp;·&nbsp;<span style={{ color: '#ff6b59', fontWeight: 700 }}>{bandCounts.Critical} Critical</span>
            &nbsp;·&nbsp;<span style={{ color: '#ffa600', fontWeight: 600 }}>{bandCounts.High} High</span>
            &nbsp;·&nbsp;{bandCounts.Medium} Medium
            &nbsp;·&nbsp;{bandCounts.Low} Low
          </p>
        </div>
      </div>

      {/* Risk Distribution Summary Bar */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ display: 'flex', height: 12, borderRadius: 6, overflow: 'hidden', width: '100%', gap: 1 }}>
          {BANDS.map(b => {
            const pct = (bandCounts[b] / total) * 100;
            if (pct === 0) return null;
            return (
              <div
                key={b}
                onClick={() => setBandFilter(bandFilter === b ? '' : b)}
                style={{
                  width: `${pct}%`,
                  background: bandColor(b),
                  cursor: 'pointer',
                  opacity: bandFilter && bandFilter !== b ? 0.3 : 1,
                  transition: 'opacity 0.2s',
                }}
                title={`${b}: ${bandCounts[b]} suppliers (${pct.toFixed(1)}%)`}
              />
            );
          })}
        </div>
        <div style={{ display: 'flex', gap: 20, marginTop: 8 }}>
          {BANDS.map(b => (
            <div
              key={b}
              onClick={() => setBandFilter(bandFilter === b ? '' : b)}
              style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', opacity: bandFilter && bandFilter !== b ? 0.5 : 1 }}
            >
              <div style={{ width: 10, height: 10, borderRadius: '50%', background: bandColor(b) }} />
              <span style={{ fontSize: 11, color: 'var(--on-surface-variant)', fontWeight: 600 }}>
                {b} ({bandCounts[b]})
              </span>
            </div>
          ))}
          {bandFilter && (
            <button
              onClick={() => setBandFilter('')}
              style={{ fontSize: 11, color: 'var(--primary)', background: 'none', border: 'none', cursor: 'pointer', marginLeft: 'auto', fontWeight: 600 }}
            >
              Clear filter ×
            </button>
          )}
        </div>
      </div>

      
      <div style={{ display: 'flex', gap: 16, marginBottom: 24 }}>
        <InsightCard title="Highest P95 Exposure" value={maxP95Supplier ? `${maxP95Supplier.supplier_name} (${fmt(maxP95Supplier.total_p95_exposure)})` : 'N/A'} />
        <InsightCard title="Critical Priority Suppliers" value={criticalCount} />
        <InsightCard title="Top Country for Critical" value={mostFreqCountry} />
        <InsightCard title="Resilience < 0.20" value={lowResilienceCount} />
      </div>

      {/* Search + Filter controls */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 24, flexWrap: 'wrap' }}>
        <input
          type="text" placeholder="Search supplier or country…" value={search}
          onChange={e => setSearch(e.target.value)}
          style={{ background: 'var(--surface-container)', border: '1px solid var(--outline-variant)', color: 'var(--on-surface)', borderRadius: 4, padding: '8px 16px', fontSize: 14, flex: '1 1 200px', outline: 'none' }}
        />
        <select
          value={bandFilter} onChange={e => setBandFilter(e.target.value)}
          style={{ background: 'var(--surface-container)', border: '1px solid var(--outline-variant)', color: 'var(--on-surface)', borderRadius: 4, padding: '8px 16px', fontSize: 14 }}
        >
          <option value="">All Risk Bands</option>
          {BANDS.map(b => <option key={b} value={b}>{b}</option>)}
        </select>
        <span className="label-caps" style={{ alignSelf: 'center', color: 'var(--on-surface-variant)' }}>
          {filtered.length} of {total} suppliers {filtered.length === 0 && '— Try adjusting your search'}
        </span>
      </div>

      
      <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
        {['Treemap', 'Triage', 'Table'].map(view => (
          <button
            key={view}
            onClick={() => setActiveView(view)}
            style={{
              padding: '6px 16px', borderRadius: 100, fontSize: 13, fontWeight: 600, border: '1px solid', cursor: 'pointer',
              background: activeView === view ? '#954e9b' : 'var(--component-bg-focus)',
              borderColor: activeView === view ? '#954e9b' : 'var(--outline-variant)',
              color: activeView === view ? 'var(--text-inverse)' : 'var(--on-surface)', transition: 'all 0.2s'
            }}
          >
            {view}
          </button>
        ))}
      </div>

      {activeView === 'Table' && (
      <div className="card" style={{ overflow: 'auto' }}>
        <table className="data-table" style={{ minWidth: 900 }}>
          <thead>
            <tr>
              <th>Supplier Name</th>
              <th>Country</th>
              <th>Tier</th>
              <th>Risk Band</th>
              <th>Priority Quadrant</th>
              <th style={{ cursor: 'pointer' }} onClick={() => toggleSort('composite_score')}>
                Composite Score (higher = riskier) {sortKey === 'composite_score' ? (sortDir === -1 ? '↓' : '↑') : ''}
              </th>
              <th style={{ cursor: 'pointer' }} onClick={() => toggleSort('resilience_score')}>
                Resilience (0–1) {sortKey === 'resilience_score' ? (sortDir === -1 ? '↓' : '↑') : ''}
              </th>
              <th style={{ cursor: 'pointer' }} onClick={() => toggleSort('total_p95_exposure')}>
                P95 Worst-Case Loss {sortKey === 'total_p95_exposure' ? (sortDir === -1 ? '↓' : '↑') : ''}
              </th>
              <th title="This supplier is the sole source for one or more products — any disruption halts production directly">
                Sole Source
              </th>
            </tr>
          </thead>
          <tbody>
            {['Critical Priority', 'Monitor Closely', 'Contingency Plan', 'Routine Review'].map(quadrant => {
              const groupData = filtered.filter(s => s.priority_quadrant === quadrant);
              if (groupData.length === 0) return null;
              
              const qColor = quadrant === 'Critical Priority' ? '#dd4d88' : quadrant === 'Monitor Closely' ? '#ff6b59' : quadrant === 'Contingency Plan' ? '#ffa600' : '#38A169';
              
              return (
                <React.Fragment key={quadrant}>
                  <tr onClick={() => toggleGroup(quadrant)} style={{ cursor: 'pointer', background: 'var(--component-bg-focus)' }}>
                    <td colSpan={9} style={{ padding: '8px 16px', fontWeight: 700, color: qColor, borderBottom: '1px solid var(--outline-variant)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span className="material-symbols-outlined" style={{ fontSize: 18, transition: 'transform 0.2s', transform: collapsedGroups[quadrant] ? 'rotate(0deg)' : 'rotate(90deg)' }}>chevron_right</span>
                        {quadrant} ({groupData.length})
                      </div>
                    </td>
                  </tr>
                  {!collapsedGroups[quadrant] && groupData.map(s => {
                    const color = bandColor(s.risk_band);
                    const isSoleSource = singleSourceSupplierIds.has(s.supplier_id);
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
                        <td style={{ color: 'var(--on-surface-variant)' }}>{s.tier != null ? `Tier ${s.tier}` : '—'}</td>
                        <td>{s.risk_band ? <RiskBadge riskBand={s.risk_band} /> : '—'}</td>
                        <td>{s.priority_quadrant ? <RiskBadge quadrant={s.priority_quadrant} /> : '—'}</td>
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <div style={{ width: 48, height: 5, borderRadius: 3, background: 'var(--surface-container-high)', overflow: 'hidden' }}>
                              <div style={{ width: `${((s.composite_score || 0) * 100).toFixed(0)}%`, height: '100%', background: color }} />
                            </div>
                            <span className="data-mono" style={{ color, fontSize: 12 }}>{s.composite_score != null ? s.composite_score.toFixed(3) : '—'}</span>
                          </div>
                        </td>
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <div style={{ width: 48, height: 5, borderRadius: 3, background: 'var(--surface-container-high)', overflow: 'hidden' }}>
                              <div style={{ width: `${((s.resilience_score || 0) * 100).toFixed(0)}%`, height: '100%', background: 'var(--primary)' }} />
                            </div>
                            <span className="data-mono" style={{ color: 'var(--primary)', fontSize: 12 }}>{s.resilience_score != null ? s.resilience_score.toFixed(3) : '—'}</span>
                          </div>
                        </td>
                        <td className="data-mono" style={{ color, fontWeight: 600 }}>{fmt(s.total_p95_exposure)}</td>
                        <td style={{ textAlign: 'center' }}>
                          {isSoleSource ? (
                            <span
                              style={{
                                display: 'inline-flex', alignItems: 'center', gap: 3,
                                background: 'rgba(255,107,89,0.12)', border: '1px solid rgba(255,107,89,0.3)',
                                color: '#ff6b59', borderRadius: 4, padding: '2px 7px', fontSize: 11, fontWeight: 700,
                              }}
                              title="This supplier is the sole source for one or more products — any disruption halts production directly"
                            >
                              <span className="material-symbols-outlined" style={{ fontSize: 12 }}>warning</span>
                              Sole Source
                            </span>
                          ) : (
                            <span style={{ color: 'var(--outline)', fontSize: 11 }}>—</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
      )}

      {activeView === 'Treemap' && (
        <div className="card card--p" style={{ padding: '16px', height: 500, overflow: 'hidden' }}>
          <ResponsiveContainer width="100%" height="100%">
            <Treemap
              data={filtered.map(s => ({
                name: s.supplier_name,
                size: s.total_p95_exposure || 1,
                actualValue: s.total_p95_exposure,
                resilience_score: s.resilience_score,
                risk_band: s.risk_band,
              }))}
              dataKey="size"
              aspectRatio={4 / 3}
              content={(props) => {
                const { x, y, width, height, name, resilience_score } = props;
                let fill = '#464c89';
                if (resilience_score < 0.25) fill = '#dd4d88';
                else if (resilience_score <= 0.40) fill = '#ff6b59';
                else if (resilience_score <= 0.55) fill = '#ffa600';
                
                const gap = 2;
                const innerWidth = Math.max(0, width - gap * 2);
                const innerHeight = Math.max(0, height - gap * 2);
                
                return (
                  <g className="treemap-cell" style={{ cursor: 'pointer' }}>
                    <rect 
                      x={x + gap} 
                      y={y + gap} 
                      width={innerWidth} 
                      height={innerHeight} 
                      rx={6} 
                      ry={6}
                      style={{ fill, stroke: 'rgba(255,255,255,0.1)', strokeWidth: 1 }} 
                    />
                  </g>
                );
              }}
            >
              <Tooltip
                cursor={false}
                content={({ active, payload }) => {
                  if (active && payload && payload.length) {
                    const data = payload[0].payload;
                    return (
                      <div style={{ 
                        background: 'rgba(26, 42, 74, 0.7)', 
                        backdropFilter: 'blur(12px)',
                        WebkitBackdropFilter: 'blur(12px)',
                        border: '1px solid rgba(255,255,255,0.15)', 
                        padding: '12px 16px', 
                        borderRadius: 12,
                        boxShadow: '0 8px 32px rgba(0,0,0,0.4)'
                      }}>
                        <div style={{ fontWeight: 700, color: 'var(--text-inverse)', marginBottom: 6, fontSize: 14 }}>{data.name}</div>
                        <div style={{ fontSize: 13, color: '#ff6b59', marginBottom: 2, fontWeight: 600 }}>Exposure: {fmt(data.actualValue)}</div>
                        <div style={{ fontSize: 12, color: 'var(--on-surface-variant)', marginBottom: 2 }}>Resilience: <span style={{color: 'var(--text-inverse)', fontWeight: 600}}>{data.resilience_score?.toFixed(3)}</span></div>
                        <div style={{ fontSize: 12, color: 'var(--on-surface-variant)' }}>Risk Band: <span style={{color: 'var(--text-inverse)', fontWeight: 600}}>{data.risk_band}</span></div>
                      </div>
                    );
                  }
                  return null;
                }}
              />
            </Treemap>
          </ResponsiveContainer>
        </div>
      )}

      {activeView === 'Triage' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {[
            { label: 'Requires Intervention', quadrantGroups: ['Critical Priority', 'Monitor Closely'], color: '#dd4d88' },
            { label: 'Watchlist', quadrantGroups: ['Contingency Plan'], color: '#ff6b59' },
            { label: 'Stable', quadrantGroups: ['Routine Review'], color: '#38A169' }
          ].map(swimlane => {
            const laneSuppliers = filtered.filter(s => swimlane.quadrantGroups.includes(s.priority_quadrant));
            return (
              <div key={swimlane.label} style={{ background: 'var(--surface-container)', borderRadius: 8, padding: 16, borderLeft: `3px solid ${swimlane.color}` }}>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12 }}>
                  <h4 style={{ margin: 0, fontSize: 14, fontWeight: 700, color: 'var(--on-surface)' }}>{swimlane.label}</h4>
                  <span style={{ background: 'var(--component-bg-focus)', padding: '2px 8px', borderRadius: 100, fontSize: 11, color: 'var(--on-surface)' }}>{laneSuppliers.length}</span>
                </div>
                <div style={{ display: 'flex', gap: 12, overflowX: 'auto', paddingBottom: 8 }}>
                  {laneSuppliers.map(s => (
                    <div key={s.supplier_id} onClick={() => navigate(`/suppliers/${s.supplier_id}`)} style={{ background: 'var(--component-bg-focus)', borderRadius: 8, padding: 12, minWidth: 200, flexShrink: 0, cursor: 'pointer' }}>
                      <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--on-surface)', marginBottom: 4 }}>{s.supplier_name}</div>
                      <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12 }}>
                        <span style={{ fontSize: 11, color: 'var(--on-surface-variant)' }}>{s.country}</span>
                        <span style={{ background: 'var(--surface-container-high)', padding: '2px 6px', borderRadius: 4, fontSize: 10, color: 'var(--on-surface-variant)' }}>Tier {s.tier}</span>
                      </div>
                      <div style={{ marginBottom: 8 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--on-surface-variant)', marginBottom: 4 }}>
                          <span>Resilience</span>
                          <span>{s.resilience_score?.toFixed(2)}</span>
                        </div>
                        <div style={{ width: '100%', height: 4, background: 'var(--surface-container-high)', borderRadius: 2, overflow: 'hidden' }}>
                          <div style={{ width: `${((s.resilience_score || 0) * 100)}%`, height: '100%', background: swimlane.color }} />
                        </div>
                      </div>
                      <div style={{ fontSize: 12, fontWeight: 700, color: swimlane.color }}>
                        {fmt(s.total_p95_exposure)}
                      </div>
                    </div>
                  ))}
                  {laneSuppliers.length === 0 && <div style={{ fontSize: 12, color: 'var(--on-surface-variant)' }}>No suppliers in this group.</div>}
                </div>
              </div>
            );
          })}
        </div>
      )}


      {/* Mini Charts */}
      {(chartCountryFilter || chartTierFilter || chartBandFilter) && (
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: -16, position: 'relative', zIndex: 10 }}>
          <button onClick={() => { setChartCountryFilter(''); setChartTierFilter(''); setChartBandFilter(''); }} style={{ background: '#dd4d88', color: 'white', border: 'none', padding: '6px 12px', borderRadius: 4, cursor: 'pointer', fontSize: 12, fontWeight: 700 }}>
            Clear Filters ×
          </button>
        </div>
      )}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginTop: 24, padding: 16, background: 'var(--surface-container)', borderRadius: 8 }}>
        
        <div style={{ height: 180 }}>
          <h5 style={{ margin: '0 0 8px 0', fontSize: 12, color: 'var(--on-surface-variant)', textAlign: 'center' }}>Top 8 Countries</h5>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={countryChartData} layout="vertical" margin={{ top: 0, right: 10, left: 10, bottom: 0 }}>
              <XAxis type="number" hide />
              <YAxis dataKey="name" type="category" axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: 'var(--on-surface-variant)' }} width={70} />
              <Bar dataKey="value" onClick={(d) => setChartCountryFilter(chartCountryFilter === d.name ? '' : d.name)} cursor="pointer" radius={[0, 4, 4, 0]}>
                {countryChartData.map((e, i) => (
                  <Cell key={`cell-${i}`} fill="var(--primary)" opacity={chartCountryFilter && chartCountryFilter !== e.name ? 0.3 : 1} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div style={{ height: 180 }}>
          <h5 style={{ margin: '0 0 8px 0', fontSize: 12, color: 'var(--on-surface-variant)', textAlign: 'center' }}>Suppliers by Tier</h5>
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={tierChartData} dataKey="value" innerRadius={45} outerRadius={65} paddingAngle={3} stroke="var(--surface-container)" strokeWidth={2} onClick={(d) => setChartTierFilter(chartTierFilter === d.name ? '' : d.name)} cursor="pointer">
                {tierChartData.map((e, i) => (
                  <Cell key={`cell-${i}`} fill={tierColors[i % tierColors.length]} opacity={chartTierFilter && chartTierFilter !== e.name ? 0.3 : 1} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ background: 'var(--tooltip-bg)', backdropFilter: 'blur(8px)', border: '1px solid var(--outline-variant)', borderRadius: 8, fontSize: 11 }} itemStyle={{ color: 'var(--text-inverse)' }} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div style={{ height: 180 }}>
          <h5 style={{ margin: '0 0 8px 0', fontSize: 12, color: 'var(--on-surface-variant)', textAlign: 'center' }}>Suppliers by Risk Band</h5>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={bandChartData} margin={{ top: 20, right: 10, left: -20, bottom: 0 }}>
              <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: 'var(--on-surface-variant)' }} />
              <YAxis hide />
              <Bar dataKey="value" onClick={(d) => setChartBandFilter(chartBandFilter === d.name ? '' : d.name)} cursor="pointer" radius={[4, 4, 0, 0]} barSize={48}>
                <LabelList dataKey="value" position="top" fill="rgba(255,255,255,0.8)" fontSize={11} fontWeight={700} />
                {bandChartData.map((e, i) => (
                  <Cell key={`cell-${i}`} fill={riskBandColors[e.name] || 'var(--primary)'} opacity={chartBandFilter && chartBandFilter !== e.name ? 0.3 : 1} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

      </div>

    </>
  );
}

