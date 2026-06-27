import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { RiskBadge } from '../components/RiskBadge';
import { LoadingSpinner, ErrorBox } from '../components/LoadingSpinner';

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
    data.sort((a, b) => sortDir * ((a[sortKey] || 0) - (b[sortKey] || 0)));
    setFiltered(data);
  }, [suppliers, search, bandFilter, sortKey, sortDir]);

  function toggleSort(key) {
    if (sortKey === key) setSortDir(d => -d);
    else { setSortKey(key); setSortDir(-1); }
  }

  if (loading) return <LoadingSpinner message="Loading supplier data…" />;
  if (error)   return <ErrorBox message={error} />;

  function fmt(n) {
    if (n == null) return '—';
    if (Math.abs(n) >= 1e7) return `₹${(n / 1e7).toFixed(1)} Cr`;
    if (Math.abs(n) >= 1e5) return `₹${(n / 1e5).toFixed(1)} L`;
    return n.toFixed(2);
  }

  // Risk distribution counts
  const BANDS = ['Critical', 'High', 'Medium', 'Low'];
  const bandCounts = {};
  BANDS.forEach(b => { bandCounts[b] = suppliers.filter(s => s.risk_band === b).length; });
  const total = suppliers.length || 1;

  return (
    <>
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
          </tbody>
        </table>
      </div>
    </>
  );
}

