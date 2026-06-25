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
  const [filtered, setFiltered] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState('');
  const [bandFilter, setBandFilter] = useState('');
  const [sortKey, setSortKey] = useState('total_p95_exposure');
  const [sortDir, setSortDir] = useState(-1);

  useEffect(() => {
    api.suppliers()
      .then(d => { setSuppliers(d); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });
  }, []);

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

  return (
    <>
      <div className="page-header">
        <h2 className="headline-lg">Supplier Risk Register</h2>
        <p>Full supplier roster with resilience scores and risk classification.</p>
      </div>

      {/* Filters */}
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
          {['Critical','High','Medium','Low'].map(b => <option key={b} value={b}>{b}</option>)}
        </select>
        <span className="label-caps" style={{ alignSelf: 'center', color: 'var(--on-surface-variant)' }}>
          {filtered.length} suppliers
        </span>
      </div>

      <div className="card" style={{ overflow: 'auto' }}>
        <table className="data-table" style={{ minWidth: 800 }}>
          <thead>
            <tr>
              <th>Supplier Name</th>
              <th>Country</th>
              <th>Tier</th>
              <th>Risk Band</th>
              <th>Priority Quadrant</th>
              <th style={{ cursor: 'pointer' }} onClick={() => toggleSort('composite_score')}>
                Composite {sortKey === 'composite_score' ? (sortDir === -1 ? '↓' : '↑') : ''}
              </th>
              <th style={{ cursor: 'pointer' }} onClick={() => toggleSort('resilience_score')}>
                Resilience {sortKey === 'resilience_score' ? (sortDir === -1 ? '↓' : '↑') : ''}
              </th>
              <th style={{ cursor: 'pointer' }} onClick={() => toggleSort('total_p95_exposure')}>
                P95 Exposure {sortKey === 'total_p95_exposure' ? (sortDir === -1 ? '↓' : '↑') : ''}
              </th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(s => {
              const color = bandColor(s.risk_band);
              return (
                <tr key={s.supplier_id} onClick={() => navigate(`/suppliers/${s.supplier_id}`)}>
                  <td><strong style={{ color: 'var(--on-surface)' }}>{s.supplier_name}</strong></td>
                  <td className="data-mono" style={{ color: 'var(--on-surface-variant)' }}>{s.country}</td>
                  <td style={{ color: 'var(--on-surface-variant)' }}>{s.tier ?? '—'}</td>
                  <td>{s.risk_band ? <RiskBadge riskBand={s.risk_band} /> : '—'}</td>
                  <td>{s.priority_quadrant ? <RiskBadge quadrant={s.priority_quadrant} /> : '—'}</td>
                  <td className="data-mono" style={{ color }}>{s.composite_score != null ? s.composite_score.toFixed(3) : '—'}</td>
                  <td className="data-mono" style={{ color: 'var(--primary)' }}>{s.resilience_score != null ? s.resilience_score.toFixed(3) : '—'}</td>
                  <td className="data-mono" style={{ color }}>{fmt(s.total_p95_exposure)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}
