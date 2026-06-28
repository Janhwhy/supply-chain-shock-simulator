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
  const [sortKey, setSortKey] = useState('highest_share');
  const [sortDir, setSortDir] = useState(-1);
  const [expanded, setExpanded] = useState({});

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
    
    const groups = data.reduce((acc, r) => {
      if (!acc[r.supplier_id]) {
        acc[r.supplier_id] = {
          supplier_id: r.supplier_id,
          supplier_name: r.supplier_name,
          country: r.country || 'Unknown',
          tier: r.tier || 2,
          products_count: 0,
          sole_source_count: 0,
          highest_share: 0,
          products: []
        };
      }
      const sup = acc[r.supplier_id];
      sup.products_count += 1;
      if (r.is_sole_source) sup.sole_source_count += 1;
      if ((r.supply_share || 0) > sup.highest_share) sup.highest_share = (r.supply_share || 0);
      sup.products.push(r);
      return acc;
    }, {});

    let groupedData = Object.values(groups);

    groupedData.sort((a, b) => {
      let valA = a[sortKey];
      let valB = b[sortKey];
      
      if (typeof valA === 'string') {
        return sortDir * valA.localeCompare(valB);
      }
      return sortDir * ((valA || 0) - (valB || 0));
    });
    
    setFiltered(groupedData);
  }, [relationships, searchSupplier, searchProduct, soleSourceFilter, sortKey, sortDir]);

  function toggleSort(key) {
    if (sortKey === key) setSortDir(d => -d);
    else {
      setSortKey(key);
      setSortDir(-1);
    }
  }

  function toggleExpand(supplierId) {
    setExpanded(prev => ({ ...prev, [supplierId]: !prev[supplierId] }));
  }

  if (loading) return <LoadingSpinner message="Loading supply relationships…" />;
  if (error)   return <ErrorBox message={error} />;

  // Metrics
  const totalRels = relationships.length;
  const soleSourceCount = relationships.filter(r => r.is_sole_source).length;
  const avgShare = relationships.reduce((acc, r) => acc + (r.supply_share || 0), 0) / (totalRels || 1);
  const uniqueSuppliers = [...new Set(relationships.map(r => r.supplier_id))].length;

  const visibleConnections = filtered.reduce((acc, sup) => acc + sup.products.length, 0);

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
        <div className="card card--p" style={{ borderLeft: '4px solid var(--primary)' }} title="Total number of supplier-to-product supply paths active in the network.">
          <div className="label-caps" style={{ color: 'var(--on-surface-variant)', display: 'flex', alignItems: 'center', gap: 4 }}>
            Active Connections
            <span className="material-symbols-outlined" style={{fontSize: 14, cursor: 'help'}}>info</span>
          </div>
          <div className="display-sm" style={{ margin: '8px 0', fontWeight: 700 }}>{totalRels}</div>
          <div className="body-xs" style={{ color: 'var(--on-surface-variant)' }}>Total supplier-to-product links</div>
        </div>
        <div className="card card--p" style={{ borderLeft: '4px solid #ff6b59' }} title="Number of products that are supplied by only one supplier.">
          <div className="label-caps" style={{ color: 'var(--on-surface-variant)', display: 'flex', alignItems: 'center', gap: 4 }}>
            Sole-Source Links
            <span className="material-symbols-outlined" style={{fontSize: 14, cursor: 'help'}}>info</span>
          </div>
          <div className="display-sm" style={{ margin: '8px 0', fontWeight: 700 }}>{soleSourceCount}</div>
          <div className="body-xs" style={{ color: 'var(--on-surface-variant)' }}>Single-point vulnerability nodes</div>
        </div>
        <div className="card card--p" style={{ borderLeft: '4px solid #ffa600' }} title="Average percentage of a product's volume that is sourced through a single link.">
          <div className="label-caps" style={{ color: 'var(--on-surface-variant)', display: 'flex', alignItems: 'center', gap: 4 }}>
            Average Supply Share
            <span className="material-symbols-outlined" style={{fontSize: 14, cursor: 'help'}}>info</span>
          </div>
          <div className="display-sm" style={{ margin: '8px 0', fontWeight: 700 }}>{(avgShare * 100).toFixed(1)}%</div>
          <div className="body-xs" style={{ color: 'var(--on-surface-variant)' }}>Mean volume allocation</div>
        </div>
        <div className="card card--p" style={{ borderLeft: '4px solid #8b91c7' }} title="Total number of distinct suppliers providing goods to the network.">
          <div className="label-caps" style={{ color: 'var(--on-surface-variant)', display: 'flex', alignItems: 'center', gap: 4 }}>
            Sourcing Suppliers
            <span className="material-symbols-outlined" style={{fontSize: 14, cursor: 'help'}}>info</span>
          </div>
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
          {visibleConnections} connections across {filtered.length} suppliers {filtered.length === 0 && '— Try adjusting your filters'}
        </span>
      </div>

      {/* Relationships Table */}
      <div className="card" style={{ overflow: 'auto' }}>
        <table className="data-table" style={{ minWidth: 800 }}>
          <thead>
            <tr>
              <th style={{ cursor: 'pointer', width: 40 }}></th>
              <th style={{ cursor: 'pointer' }} onClick={() => toggleSort('supplier_name')}>
                Supplier Name {sortKey === 'supplier_name' ? (sortDir === -1 ? '↓' : '↑') : ''}
              </th>
              <th style={{ cursor: 'pointer' }} onClick={() => toggleSort('country')}>
                Country {sortKey === 'country' ? (sortDir === -1 ? '↓' : '↑') : ''}
              </th>
              <th style={{ cursor: 'pointer' }} onClick={() => toggleSort('tier')}>
                Tier {sortKey === 'tier' ? (sortDir === -1 ? '↓' : '↑') : ''}
              </th>
              <th style={{ cursor: 'pointer' }} onClick={() => toggleSort('products_count')}>
                Products Supplied {sortKey === 'products_count' ? (sortDir === -1 ? '↓' : '↑') : ''}
              </th>
              <th style={{ cursor: 'pointer' }} onClick={() => toggleSort('sole_source_count')}>
                Sole-Source Links {sortKey === 'sole_source_count' ? (sortDir === -1 ? '↓' : '↑') : ''}
              </th>
              <th style={{ cursor: 'pointer' }} onClick={() => toggleSort('highest_share')}>
                Highest Share {sortKey === 'highest_share' ? (sortDir === -1 ? '↓' : '↑') : ''}
              </th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(sup => (
              <React.Fragment key={sup.supplier_id}>
                <tr onClick={() => toggleExpand(sup.supplier_id)} style={{ cursor: 'pointer', background: expanded[sup.supplier_id] ? 'var(--surface-container-high)' : 'transparent' }}>
                  <td style={{ color: 'var(--on-surface-variant)', userSelect: 'none' }}>
                    <span className="material-symbols-outlined" style={{ fontSize: 18, verticalAlign: 'middle', transition: 'transform 0.2s', transform: expanded[sup.supplier_id] ? 'rotate(90deg)' : 'rotate(0deg)' }}>
                      chevron_right
                    </span>
                  </td>
                  <td><strong style={{ color: 'var(--on-surface)' }}>{sup.supplier_name}</strong></td>
                  <td style={{ color: 'var(--on-surface)' }}>{sup.country}</td>
                  <td style={{ color: 'var(--on-surface)' }}>Tier {sup.tier}</td>
                  <td style={{ color: 'var(--on-surface)' }}>{sup.products_count}</td>
                  <td>
                    {sup.sole_source_count > 0 ? (
                      <span style={{ color: '#ff6b59', fontWeight: 600 }}>{sup.sole_source_count} ⚠️</span>
                    ) : (
                      <span style={{ color: 'var(--on-surface-variant)' }}>0</span>
                    )}
                  </td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                      <div style={{ flex: 1, background: 'var(--surface-container-highest)', height: 8, borderRadius: 4, overflow: 'hidden', minWidth: 60, maxWidth: 100 }}>
                        <div 
                          style={{ 
                            background: sup.highest_share > 0.7 ? '#ff6b59' : (sup.highest_share >= 0.4 ? '#ffa600' : '#4299e1'), 
                            height: '100%', 
                            width: `${sup.highest_share * 100}%` 
                          }} 
                        />
                      </div>
                      <span className="data-mono" style={{ minWidth: 45, textAlign: 'right' }}>
                        {(sup.highest_share * 100).toFixed(0)}%
                      </span>
                    </div>
                  </td>
                </tr>
                {expanded[sup.supplier_id] && (
                  <tr>
                    <td colSpan="7" style={{ padding: 0, border: 'none' }}>
                      <div style={{ background: 'var(--surface)', padding: '16px 24px 16px 64px', borderBottom: '1px solid var(--outline-variant)', borderLeft: '4px solid var(--primary)' }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                          <thead>
                            <tr>
                              <th style={{ textAlign: 'left', paddingBottom: 8, color: 'var(--on-surface-variant)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Product SKU / Name</th>
                              <th style={{ textAlign: 'left', paddingBottom: 8, color: 'var(--on-surface-variant)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Supply Share</th>
                              <th style={{ textAlign: 'left', paddingBottom: 8, color: 'var(--on-surface-variant)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Sourcing Category</th>
                            </tr>
                          </thead>
                          <tbody>
                            {sup.products.map(r => (
                              <tr key={r.relationship_id}>
                                <td style={{ padding: '8px 0', borderBottom: '1px solid var(--outline-variant)' }}>
                                  <div style={{ display: 'flex', flexDirection: 'column' }}>
                                    <span className="data-mono" style={{ color: 'var(--primary)', fontWeight: 600 }}>{r.sku}</span>
                                    <span className="body-xs" style={{ color: 'var(--on-surface-variant)' }}>{r.product_name}</span>
                                  </div>
                                </td>
                                <td style={{ padding: '8px 0', borderBottom: '1px solid var(--outline-variant)', minWidth: 200 }}>
                                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                                    <div style={{ flex: 1, background: 'var(--surface-container-high)', height: 6, borderRadius: 3, overflow: 'hidden', maxWidth: 120 }}>
                                      <div 
                                        style={{ 
                                          background: r.supply_share > 0.7 ? '#ff6b59' : (r.supply_share >= 0.4 ? '#ffa600' : '#4299e1'), 
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
                                <td style={{ padding: '8px 0', borderBottom: '1px solid var(--outline-variant)' }}>
                                  {r.is_sole_source ? (
                                    <span style={{
                                      background: 'rgba(255, 107, 89, 0.15)',
                                      color: '#ff6b59',
                                      padding: '4px 10px',
                                      borderRadius: 100,
                                      fontSize: 11,
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
                                      fontSize: 11,
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
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan="7" style={{ textAlign: 'center', padding: '40px 0', color: 'var(--on-surface-variant)' }}>
                  No relationships match your search. Try clearing your filters or searching for a different supplier.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}
