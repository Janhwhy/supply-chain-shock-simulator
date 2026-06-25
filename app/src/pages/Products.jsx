import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { LoadingSpinner, ErrorBox } from '../components/LoadingSpinner';

export function Products() {
  const [products, setProducts] = useState([]);
  const [filtered, setFiltered] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [sortKey, setSortKey] = useState('monthly_demand');
  const [sortDir, setSortDir] = useState(-1);

  useEffect(() => {
    api.products()
      .then(d => {
        setProducts(d);
        setLoading(false);
      })
      .catch(e => {
        setError(e.message);
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    let data = [...products];
    if (search) {
      const q = search.toLowerCase();
      data = data.filter(p => 
        p.product_name?.toLowerCase().includes(q) || 
        p.sku?.toLowerCase().includes(q)
      );
    }
    if (categoryFilter) {
      data = data.filter(p => p.category?.toLowerCase() === categoryFilter.toLowerCase());
    }
    
    data.sort((a, b) => {
      let valA = a[sortKey];
      let valB = b[sortKey];
      
      if (typeof valA === 'string') {
        return sortDir * valA.localeCompare(valB);
      }
      return sortDir * ((valA || 0) - (valB || 0));
    });
    
    setFiltered(data);
  }, [products, search, categoryFilter, sortKey, sortDir]);

  function toggleSort(key) {
    if (sortKey === key) setSortDir(d => -d);
    else {
      setSortKey(key);
      setSortDir(-1);
    }
  }

  if (loading) return <LoadingSpinner message="Loading products catalog…" />;
  if (error)   return <ErrorBox message={error} />;

  // Metrics
  const totalProducts = products.length;
  const categories = [...new Set(products.map(p => p.category))].filter(Boolean);
  const avgCost = products.reduce((acc, p) => acc + (p.unit_cost || 0), 0) / (totalProducts || 1);
  const totalMonthlyDemand = products.reduce((acc, p) => acc + (p.monthly_demand || 0), 0);

  function fmtCost(n) {
    if (n == null) return '—';
    return `₹${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }

  function fmtDemand(n) {
    if (n == null) return '—';
    return n.toLocaleString();
  }

  return (
    <>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24 }}>
        <h2 className="headline-lg">Products Catalog</h2>
        <p className="body-sm" style={{ color: 'var(--on-surface-variant)' }}>
          Detailed list of manufactured and sourced parts, assembly specifications, and demands.
        </p>
      </div>

      {/* KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 16, marginBottom: 24 }}>
        <div className="card card--p" style={{ borderLeft: '4px solid var(--primary)' }}>
          <div className="label-caps" style={{ color: 'var(--on-surface-variant)' }}>Total SKUs</div>
          <div className="display-sm" style={{ margin: '8px 0', fontWeight: 700 }}>{totalProducts}</div>
          <div className="body-xs" style={{ color: 'var(--on-surface-variant)' }}>Unique product definitions</div>
        </div>
        <div className="card card--p" style={{ borderLeft: '4px solid #8b91c7' }}>
          <div className="label-caps" style={{ color: 'var(--on-surface-variant)' }}>Categories</div>
          <div className="display-sm" style={{ margin: '8px 0', fontWeight: 700 }}>{categories.length}</div>
          <div className="body-xs" style={{ color: 'var(--on-surface-variant)' }}>Sourcing categories</div>
        </div>
        <div className="card card--p" style={{ borderLeft: '4px solid #ffa600' }}>
          <div className="label-caps" style={{ color: 'var(--on-surface-variant)' }}>Avg Unit Cost</div>
          <div className="display-sm" style={{ margin: '8px 0', fontWeight: 700 }}>{fmtCost(avgCost)}</div>
          <div className="body-xs" style={{ color: 'var(--on-surface-variant)' }}>Average price across items</div>
        </div>
        <div className="card card--p" style={{ borderLeft: '4px solid #ff6b59' }}>
          <div className="label-caps" style={{ color: 'var(--on-surface-variant)' }}>Total Monthly Demand</div>
          <div className="display-sm" style={{ margin: '8px 0', fontWeight: 700 }}>{fmtDemand(totalMonthlyDemand)}</div>
          <div className="body-xs" style={{ color: 'var(--on-surface-variant)' }}>Aggregated units ordered/month</div>
        </div>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap', alignItems: 'center' }}>
        <input
          type="text"
          placeholder="Search by SKU or Product Name…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{
            background: 'var(--surface-container)',
            border: '1px solid var(--outline-variant)',
            color: 'var(--on-surface)',
            borderRadius: 6,
            padding: '10px 16px',
            fontSize: 14,
            flex: '1 1 250px',
            outline: 'none'
          }}
        />
        <select
          value={categoryFilter}
          onChange={e => setCategoryFilter(e.target.value)}
          style={{
            background: 'var(--surface-container)',
            border: '1px solid var(--outline-variant)',
            color: 'var(--on-surface)',
            borderRadius: 6,
            padding: '10px 16px',
            fontSize: 14,
            outline: 'none'
          }}
        >
          <option value="">All Categories</option>
          {categories.map(cat => (
            <option key={cat} value={cat}>{cat}</option>
          ))}
        </select>
        <span className="label-caps" style={{ color: 'var(--on-surface-variant)', marginLeft: 'auto' }}>
          {filtered.length} products listed
        </span>
      </div>

      {/* Catalog Table */}
      <div className="card" style={{ overflow: 'auto' }}>
        <table className="data-table" style={{ minWidth: 800 }}>
          <thead>
            <tr>
              <th style={{ cursor: 'pointer' }} onClick={() => toggleSort('sku')}>
                SKU {sortKey === 'sku' ? (sortDir === -1 ? '↓' : '↑') : ''}
              </th>
              <th style={{ cursor: 'pointer' }} onClick={() => toggleSort('product_name')}>
                Product Name {sortKey === 'product_name' ? (sortDir === -1 ? '↓' : '↑') : ''}
              </th>
              <th style={{ cursor: 'pointer' }} onClick={() => toggleSort('category')}>
                Category {sortKey === 'category' ? (sortDir === -1 ? '↓' : '↑') : ''}
              </th>
              <th style={{ cursor: 'pointer', textAlign: 'right' }} onClick={() => toggleSort('unit_cost')}>
                Unit Cost {sortKey === 'unit_cost' ? (sortDir === -1 ? '↓' : '↑') : ''}
              </th>
              <th style={{ cursor: 'pointer', textAlign: 'right' }} onClick={() => toggleSort('monthly_demand')}>
                Monthly Demand {sortKey === 'monthly_demand' ? (sortDir === -1 ? '↓' : '↑') : ''}
              </th>
              <th style={{ cursor: 'pointer', textAlign: 'right' }} onClick={() => toggleSort('safety_stock_days')}>
                Safety Stock (Days) {sortKey === 'safety_stock_days' ? (sortDir === -1 ? '↓' : '↑') : ''}
              </th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(p => (
              <tr key={p.product_id}>
                <td className="data-mono" style={{ color: 'var(--primary)', fontWeight: 600 }}>{p.sku}</td>
                <td><strong style={{ color: 'var(--on-surface)' }}>{p.product_name}</strong></td>
                <td>
                  <span style={{
                    background: 'var(--surface-container-high)',
                    padding: '2px 8px',
                    borderRadius: 4,
                    fontSize: 12,
                    color: 'var(--on-surface-variant)'
                  }}>
                    {p.category}
                  </span>
                </td>
                <td className="data-mono" style={{ textAlign: 'right', color: 'var(--on-surface)' }}>
                  {fmtCost(p.unit_cost)}
                </td>
                <td className="data-mono" style={{ textAlign: 'right', color: 'var(--on-surface)' }}>
                  {fmtDemand(p.monthly_demand)}
                </td>
                <td className="data-mono" style={{ textAlign: 'right', color: 'var(--on-surface-variant)' }}>
                  {p.safety_stock_days != null ? `${p.safety_stock_days} Days` : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
