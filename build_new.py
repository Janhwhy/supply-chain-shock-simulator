import re

with open('app/src/pages/SupplierRisk.jsx', 'r') as f:
    content = f.read()

# 1. Imports
import_statement = "import { Treemap, Tooltip, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, PieChart, Pie, Cell } from 'recharts';\n"
content = content.replace("import { LoadingSpinner, ErrorBox } from '../components/LoadingSpinner';", "import { LoadingSpinner, ErrorBox } from '../components/LoadingSpinner';\n" + import_statement)

# 2. State
state_code = """
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
"""
content = content.replace("const [sortDir, setSortDir] = useState(-1);", "const [sortDir, setSortDir] = useState(-1);\n" + state_code)

# 3. Filtering logic
filter_logic = """
    if (chartCountryFilter) data = data.filter(s => s.country === chartCountryFilter);
    if (chartTierFilter) data = data.filter(s => String(s.tier) === chartTierFilter);
    if (chartBandFilter) data = data.filter(s => s.risk_band === chartBandFilter);
"""
content = content.replace("data.sort((a, b) => sortDir * ((a[sortKey] || 0) - (b[sortKey] || 0)));", filter_logic + "    data.sort((a, b) => sortDir * ((a[sortKey] || 0) - (b[sortKey] || 0)));")
content = content.replace("[suppliers, search, bandFilter, sortKey, sortDir]", "[suppliers, search, bandFilter, sortKey, sortDir, chartCountryFilter, chartTierFilter, chartBandFilter]")

# 4. Insight Cards
insights_code = """
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
    <div style={{ background: '#1a2a4a', borderLeft: '3px solid #dd4d88', borderRadius: 8, padding: 12, flex: 1 }}>
      <div style={{ fontSize: 11, color: 'var(--on-surface-variant)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{title}</div>
      <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--on-surface)' }}>{value}</div>
    </div>
  );
"""
content = content.replace("function fmt(n) {", insights_code + "\n  function fmt(n) {")

insight_cards_ui = """
      <div style={{ display: 'flex', gap: 16, marginBottom: 24 }}>
        <InsightCard title="Highest P95 Exposure" value={maxP95Supplier ? `${maxP95Supplier.supplier_name} (${fmt(maxP95Supplier.total_p95_exposure)})` : 'N/A'} />
        <InsightCard title="Critical Priority Suppliers" value={criticalCount} />
        <InsightCard title="Top Country for Critical" value={mostFreqCountry} />
        <InsightCard title="Resilience < 0.20" value={lowResilienceCount} />
      </div>
"""
content = content.replace("{/* Search + Filter controls */}", insight_cards_ui + "\n      {/* Search + Filter controls */}")

# 5. View Toggles
view_toggles_ui = """
      <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
        {['Treemap', 'Triage', 'Table'].map(view => (
          <button
            key={view}
            onClick={() => setActiveView(view)}
            style={{
              padding: '6px 16px', borderRadius: 100, fontSize: 13, fontWeight: 600, border: '1px solid', cursor: 'pointer',
              background: activeView === view ? '#954e9b' : '#1a2a4a',
              borderColor: activeView === view ? '#954e9b' : '#464c89',
              color: 'white', transition: 'all 0.2s'
            }}
          >
            {view}
          </button>
        ))}
      </div>
"""
content = content.replace("<div className=\"card\" style={{ overflow: 'auto' }}>", view_toggles_ui + "\n      <div className=\"card\" style={{ overflow: 'auto' }}>")

# 6. Table replacement (collapsible sections)
old_tbody = """          <tbody>
            {filtered.map(s => {
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
          </tbody>"""

new_tbody = """          <tbody>
            {['Critical Priority', 'Monitor Closely', 'Contingency Plan', 'Routine Review'].map(quadrant => {
              const groupData = filtered.filter(s => s.priority_quadrant === quadrant);
              if (groupData.length === 0) return null;
              
              const qColor = quadrant === 'Critical Priority' ? '#dd4d88' : quadrant === 'Monitor Closely' ? '#ff6b59' : quadrant === 'Contingency Plan' ? '#ffa600' : '#38A169';
              
              return (
                <React.Fragment key={quadrant}>
                  <tr onClick={() => toggleGroup(quadrant)} style={{ cursor: 'pointer', background: '#1a2a4a' }}>
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
          </tbody>"""

content = content.replace(old_tbody, new_tbody)

content = content.replace("<div className=\"card\" style={{ overflow: 'auto' }}>", "{activeView === 'Table' && (\n      <div className=\"card\" style={{ overflow: 'auto' }}>")
content = content.replace("        </table>\n      </div>", "        </table>\n      </div>\n      )}")

# 7. Add Treemap and Triage views
views_code = """
      {activeView === 'Treemap' && (
        <div className="card card--p" style={{ padding: '16px', height: 500 }}>
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
                return (
                  <g>
                    <rect x={x} y={y} width={width} height={height} style={{ fill, stroke: '#1a2a4a', strokeWidth: 1 }} />
                  </g>
                );
              }}
            >
              <Tooltip
                content={({ active, payload }) => {
                  if (active && payload && payload.length) {
                    const data = payload[0].payload;
                    return (
                      <div style={{ background: '#1a2a4a', border: '1px solid #464c89', padding: 12, borderRadius: 8 }}>
                        <div style={{ fontWeight: 700, color: 'white', marginBottom: 4 }}>{data.name}</div>
                        <div style={{ fontSize: 12, color: '#ff6b59', marginBottom: 2 }}>Exposure: {fmt(data.actualValue)}</div>
                        <div style={{ fontSize: 12, color: 'var(--on-surface-variant)' }}>Resilience: {data.resilience_score?.toFixed(3)}</div>
                        <div style={{ fontSize: 12, color: 'var(--on-surface-variant)' }}>Risk Band: {data.risk_band}</div>
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
                  <span style={{ background: '#1a2a4a', padding: '2px 8px', borderRadius: 100, fontSize: 11, color: 'var(--on-surface)' }}>{laneSuppliers.length}</span>
                </div>
                <div style={{ display: 'flex', gap: 12, overflowX: 'auto', paddingBottom: 8 }}>
                  {laneSuppliers.map(s => (
                    <div key={s.supplier_id} onClick={() => navigate(`/suppliers/${s.supplier_id}`)} style={{ background: '#1a2a4a', borderRadius: 8, padding: 12, minWidth: 200, flexShrink: 0, cursor: 'pointer' }}>
                      <div style={{ fontWeight: 700, fontSize: 13, color: 'white', marginBottom: 4 }}>{s.supplier_name}</div>
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
"""
content = content.replace("        </table>\n      </div>\n      )}", "        </table>\n      </div>\n      )}\n" + views_code)


# 8. Mini Charts
charts_logic = """
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
"""
content = content.replace("const BANDS = ['Critical', 'High', 'Medium', 'Low'];", "const BANDS = ['Critical', 'High', 'Medium', 'Low'];\n" + charts_logic)

charts_ui = """
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
              <Bar dataKey="value" onClick={(d) => setChartCountryFilter(chartCountryFilter === d.name ? '' : d.name)} cursor="pointer">
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
              <Pie data={tierChartData} dataKey="value" innerRadius={40} outerRadius={60} paddingAngle={2} onClick={(d) => setChartTierFilter(chartTierFilter === d.name ? '' : d.name)} cursor="pointer">
                {tierChartData.map((e, i) => (
                  <Cell key={`cell-${i}`} fill={tierColors[i % tierColors.length]} opacity={chartTierFilter && chartTierFilter !== e.name ? 0.3 : 1} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ background: '#1a2a4a', border: 'none', borderRadius: 4, fontSize: 11 }} itemStyle={{ color: 'white' }} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div style={{ height: 180 }}>
          <h5 style={{ margin: '0 0 8px 0', fontSize: 12, color: 'var(--on-surface-variant)', textAlign: 'center' }}>Suppliers by Risk Band</h5>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={bandChartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: 'var(--on-surface-variant)' }} />
              <YAxis hide />
              <Bar dataKey="value" onClick={(d) => setChartBandFilter(chartBandFilter === d.name ? '' : d.name)} cursor="pointer">
                {bandChartData.map((e, i) => (
                  <Cell key={`cell-${i}`} fill={riskBandColors[e.name] || 'var(--primary)'} opacity={chartBandFilter && chartBandFilter !== e.name ? 0.3 : 1} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

      </div>
"""
# Need to inject this exactly before the final `</>`
content = content.replace("    </>\n  );\n}", charts_ui + "\n    </>\n  );\n}")

with open('app/src/pages/SupplierRisk.jsx', 'w') as f:
    f.write(content)
