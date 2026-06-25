import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { LoadingSpinner, ErrorBox } from '../components/LoadingSpinner';

export function Relationships() {
  const [relationships, setRelationships] = useState([]);
  const [filtered, setFiltered] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchSupplier, setSearchSupplier] = useState('');
  const [searchProduct, setSearchProduct] = useState('');
  const [soleSourceFilter, setSoleSourceFilter] = useState('');
  const [sortKey, setSortKey] = useState('supply_share');
  const [sortDir, setSortDir] = useState(-1);

  useEffect(() => {
    api.relationships()
      .then(d => {
        setRelationships(d);
        setLoading(false);
      })
      .catch(e => {
        setError(e.message);
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    let data = [...relationships];
    if (searchSupplier) {
      const q = searchSupplier.toLowerCase();
      data = data.filter(r => r.supplier_name?.toLowerCase().includes(q));
    }
    if (searchProduct) {
      const q = searchProduct.toLowerCase();
      data = data.filter(r => 
        r.product_name?.toLowerCase().includes(q) || 
        r.sku?.toLowerCase().includes(q)
      );
    }
    if (soleSourceFilter) {
      const isSole = soleSourceFilter === 'yes';
      data = data.filter(r => r.is_sole_source === isSole);
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
  }, [relationships, searchSupplier, searchProduct, soleSourceFilter, sortKey, sortDir]);

  function toggleSort(key) {
    if (sortKey === key) setSortDir(d => -d);
    else {
      setSortKey(key);
      setSortDir(-1);
    }
  }

  if (loading) return <LoadingSpinner message="Loading supply relationships…" />;
  if (error)   return <ErrorBox message={error} />;

  // Metrics
  const totalRels = relationships.length;
  const soleSourceCount = relationships.filter(r => r.is_sole_source).length;
  const avgShare = relationships.reduce((acc, r) => acc + (r.supply_share || 0), 0) / (totalRels || 1);
  const uniqueSuppliers = [...new Set(relationships.map(r => r.supplier_id))].length;

  return (
    <>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24 }}>
        <h2 className="headline-lg">Supply Relationships</h2>
        <p className="body-sm" style={{ color: 'var(--on-surface-variant)' }}>
          Detailed mapping of which suppliers supply which products, including volume share and dependency flags.
        </p>
      </div>

      {/* KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 16, marginBottom: 24 }}>
        <div className="card card--p" style={{ borderLeft: '4px solid var(--primary)' }}>
          <div className="label-caps" style={{ color: 'var(--on-surface-variant)' }}>Active Connections</div>
          <div className="display-sm" style={{ margin: '8px 0', fontWeight: 700 }}>{totalRels}</div>
          <div className="body-xs" style={{ color: 'var(--on-surface-variant)' }}>Total supplier-to-product links</div>
        </div>
        <div className="card card--p" style={{ borderLeft: '4px solid #ff6b59' }}>
          <div className="label-caps" style={{ color: 'var(--on-surface-variant)' }}>Sole-Source Links</div>
          <div className="display-sm" style={{ margin: '8px 0', fontWeight: 700 }}>{soleSourceCount}</div>
          <div className="body-xs" style={{ color: 'var(--on-surface-variant)' }}>Single-point vulnerability nodes</div>
        </div>
        <div className="card card--p" style={{ borderLeft: '4px solid #ffa600' }}>
          <div className="label-caps" style={{ color: 'var(--on-surface-variant)' }}>Average Supply Share</div>
          <div className="display-sm" style={{ margin: '8px 0', fontWeight: 700 }}>{(avgShare * 100).toFixed(1)}%</div>
          <div className="body-xs" style={{ color: 'var(--on-surface-variant)' }}>Mean volume allocation</div>
        </div>
        <div className="card card--p" style={{ borderLeft: '4px solid #8b91c7' }}>
          <div className="label-caps" style={{ color: 'var(--on-surface-variant)' }}>Sourcing Suppliers</div>
          <div className="display-sm" style={{ margin: '8px 0', fontWeight: 700 }}>{uniqueSuppliers}</div>
          <div className="body-xs" style={{ color: 'var(--on-surface-variant)' }}>Suppliers with active relations</div>
        </div>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap', alignItems: 'center' }}>
        <input
          type="text"
          placeholder="Filter by Supplier Name…"
          value={searchSupplier}
          onChange={e => setSearchSupplier(e.target.value)}
          style={{
            background: 'var(--surface-container)',
            border: '1px solid var(--outline-variant)',
            color: 'var(--on-surface)',
            borderRadius: 6,
            padding: '10px 16px',
            fontSize: 14,
            flex: '1 1 200px',
            outline: 'none'
          }}
        />
        <input
          type="text"
          placeholder="Filter by SKU or Product Name…"
          value={searchProduct}
          onChange={e => setSearchProduct(e.target.value)}
          style={{
            background: 'var(--surface-container)',
            border: '1px solid var(--outline-variant)',
            color: 'var(--on-surface)',
            borderRadius: 6,
            padding: '10px 16px',
            fontSize: 14,
            flex: '1 1 200px',
            outline: 'none'
          }}
        />
        <select
          value={soleSourceFilter}
          onChange={e => setSoleSourceFilter(e.target.value)}
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
          <option value="">All Sourcing Types</option>
          <option value="yes">Sole Source Only</option>
          <option value="no">Multi-Source Only</option>
        </select>
        <span className="label-caps" style={{ color: 'var(--on-surface-variant)', marginLeft: 'auto' }}>
          {filtered.length} connections showing
        </span>
      </div>

      {/* Relationships Table */}
      <div className="card" style={{ overflow: 'auto' }}>
        <table className="data-table" style={{ minWidth: 800 }}>
          <thead>
            <tr>
              <th style={{ cursor: 'pointer' }} onClick={() => toggleSort('relationship_id')}>
                Rel ID {sortKey === 'relationship_id' ? (sortDir === -1 ? '↓' : '↑') : ''}
              </th>
              <th style={{ cursor: 'pointer' }} onClick={() => toggleSort('supplier_name')}>
                Supplier Name {sortKey === 'supplier_name' ? (sortDir === -1 ? '↓' : '↑') : ''}
              </th>
              <th style={{ cursor: 'pointer' }} onClick={() => toggleSort('sku')}>
                Product SKU / Name {sortKey === 'sku' ? (sortDir === -1 ? '↓' : '↑') : ''}
              </th>
              <th style={{ cursor: 'pointer' }} onClick={() => toggleSort('supply_share')}>
                Supply Share {sortKey === 'supply_share' ? (sortDir === -1 ? '↓' : '↑') : ''}
              </th>
              <th style={{ cursor: 'pointer' }} onClick={() => toggleSort('is_sole_source')}>
                Sourcing Category {sortKey === 'is_sole_source' ? (sortDir === -1 ? '↓' : '↑') : ''}
              </th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(r => (
              <tr key={r.relationship_id}>
                <td className="data-mono" style={{ color: 'var(--on-surface-variant)' }}>#{r.relationship_id}</td>
                <td><strong style={{ color: 'var(--on-surface)' }}>{r.supplier_name}</strong></td>
                <td>
                  <div style={{ display: 'flex', flexDirection: 'column' }}>
                    <span className="data-mono" style={{ color: 'var(--primary)', fontWeight: 600 }}>{r.sku}</span>
                    <span className="body-xs" style={{ color: 'var(--on-surface-variant)' }}>{r.product_name}</span>
                  </div>
                </td>
                <td>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <div style={{ flex: 1, background: 'var(--surface-container-high)', height: 8, borderRadius: 4, overflow: 'hidden', minWidth: 80 }}>
                      <div 
                        style={{ 
                          background: r.is_sole_source ? '#ff6b59' : 'var(--primary)', 
                          height: '100%', 
                          width: `${(r.supply_share || 0) * 100}%` 
                        }} 
                      />
                    </div>
                    <span className="data-mono" style={{ minWidth: 45, textAlign: 'right' }}>
                      {((r.supply_share || 0) * 100).toFixed(0)}%
                    </span>
                  </div>
                </td>
                <td>
                  {r.is_sole_source ? (
                    <span style={{
                      background: 'rgba(255, 107, 89, 0.15)',
                      color: '#ff6b59',
                      padding: '4px 10px',
                      borderRadius: 100,
                      fontSize: 12,
                      fontWeight: 600,
                      border: '1px solid rgba(255, 107, 89, 0.3)'
                    }}>
                      Sole Source
                    </span>
                  ) : (
                    <span style={{
                      background: 'rgba(66, 153, 225, 0.15)',
                      color: '#4299e1',
                      padding: '4px 10px',
                      borderRadius: 100,
                      fontSize: 12,
                      fontWeight: 600,
                      border: '1px solid rgba(66, 153, 225, 0.3)'
                    }}>
                      Multi-Source
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
