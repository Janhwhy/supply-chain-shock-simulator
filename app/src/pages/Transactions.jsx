import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { LoadingSpinner, ErrorBox } from '../components/LoadingSpinner';

export function Transactions() {
  const [transactions, setTransactions] = useState([]);
  const [filtered, setFiltered] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchSupplier, setSearchSupplier] = useState('');
  const [searchProduct, setSearchProduct] = useState('');
  const [delayOnly, setDelayOnly] = useState(false);
  const [rejectionsOnly, setRejectionsOnly] = useState(false);
  const [sortKey, setSortKey] = useState('order_date');
  const [sortDir, setSortDir] = useState(-1);
  const [limit, setLimit] = useState(150);

  useEffect(() => {
    setLoading(true);
    api.transactions({ limit })
      .then(d => {
        setTransactions(d);
        setLoading(false);
      })
      .catch(e => {
        setError(e.message);
        setLoading(false);
      });
  }, [limit]);

  useEffect(() => {
    let data = [...transactions].map(t => {
      // Calculate delay in days
      let delayDays = 0;
      if (t.actual_delivery_date && t.promised_delivery_date) {
        const promised = new Date(t.promised_delivery_date);
        const actual = new Date(t.actual_delivery_date);
        delayDays = Math.max(0, Math.round((actual - promised) / (1000 * 60 * 60 * 24)));
      }
      // Calculate rejection percentage
      const rejectionRate = t.quantity_ordered > 0 ? (t.quantity_rejected / t.quantity_ordered) * 100 : 0;
      return { ...t, delayDays, rejectionRate };
    });

    if (searchSupplier) {
      const q = searchSupplier.toLowerCase();
      data = data.filter(t => t.supplier_name?.toLowerCase().includes(q));
    }
    if (searchProduct) {
      const q = searchProduct.toLowerCase();
      data = data.filter(t => 
        t.product_name?.toLowerCase().includes(q) || 
        t.sku?.toLowerCase().includes(q)
      );
    }
    if (delayOnly) {
      data = data.filter(t => t.delayDays > 0);
    }
    if (rejectionsOnly) {
      data = data.filter(t => t.quantity_rejected > 0);
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
  }, [transactions, searchSupplier, searchProduct, delayOnly, rejectionsOnly, sortKey, sortDir]);

  function toggleSort(key) {
    if (sortKey === key) setSortDir(d => -d);
    else {
      setSortKey(key);
      setSortDir(-1);
    }
  }

  if (loading) return <LoadingSpinner message="Loading transaction logs…" />;
  if (error)   return <ErrorBox message={error} />;

  // Calculate high-level performance metrics based on visible transactions
  const totalOrders = transactions.length;
  const delayedOrders = transactions.filter(t => {
    if (!t.actual_delivery_date || !t.promised_delivery_date) return false;
    return new Date(t.actual_delivery_date) > new Date(t.promised_delivery_date);
  }).length;
  const onTimeDeliveryRate = totalOrders > 0 ? ((totalOrders - delayedOrders) / totalOrders) * 100 : 100;

  const totalQtyOrdered = transactions.reduce((acc, t) => acc + (t.quantity_ordered || 0), 0);
  const totalQtyRejected = transactions.reduce((acc, t) => acc + (t.quantity_rejected || 0), 0);
  const avgRejectionRate = totalQtyOrdered > 0 ? (totalQtyRejected / totalQtyOrdered) * 100 : 0;

  const avgDelay = transactions.reduce((acc, t) => {
    if (!t.actual_delivery_date || !t.promised_delivery_date) return acc;
    const diff = (new Date(t.actual_delivery_date) - new Date(t.promised_delivery_date)) / (1000 * 60 * 60 * 24);
    return acc + Math.max(0, diff);
  }, 0) / (totalOrders || 1);

  function fmtDate(d) {
    if (!d) return '—';
    return new Date(d).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  }

  function fmtNumber(n) {
    if (n == null) return '—';
    return n.toLocaleString();
  }

  return (
    <>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24 }}>
        <h2 className="headline-lg">Transaction Log</h2>
        <p className="body-sm" style={{ color: 'var(--on-surface-variant)' }}>
          Historical record of purchase orders, delivery times, and quality rejection metrics across all suppliers.
        </p>
      </div>

      {/* KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 16, marginBottom: 24 }}>
        <div className="card card--p" style={{ borderLeft: '4px solid var(--primary)' }}>
          <div className="label-caps" style={{ color: 'var(--on-surface-variant)' }}>On-Time Delivery (OTDR)</div>
          <div className="display-sm" style={{ margin: '8px 0', fontWeight: 700, color: onTimeDeliveryRate < 80 ? '#ff6b59' : 'var(--primary)' }}>
            {onTimeDeliveryRate.toFixed(1)}%
          </div>
          <div className="body-xs" style={{ color: 'var(--on-surface-variant)' }}>Orders arriving by promise date</div>
        </div>
        <div className="card card--p" style={{ borderLeft: '4px solid #ff6b59' }}>
          <div className="label-caps" style={{ color: 'var(--on-surface-variant)' }}>Defect Rejection Rate</div>
          <div className="display-sm" style={{ margin: '8px 0', fontWeight: 700, color: avgRejectionRate > 2 ? '#ff6b59' : 'var(--on-surface)' }}>
            {avgRejectionRate.toFixed(2)}%
          </div>
          <div className="body-xs" style={{ color: 'var(--on-surface-variant)' }}>Total rejected units fraction</div>
        </div>
        <div className="card card--p" style={{ borderLeft: '4px solid #ffa600' }}>
          <div className="label-caps" style={{ color: 'var(--on-surface-variant)' }}>Average Delay Time</div>
          <div className="display-sm" style={{ margin: '8px 0', fontWeight: 700 }}>{avgDelay.toFixed(1)} Days</div>
          <div className="body-xs" style={{ color: 'var(--on-surface-variant)' }}>Mean delivery schedule slip</div>
        </div>
        <div className="card card--p" style={{ borderLeft: '4px solid #8b91c7' }}>
          <div className="label-caps" style={{ color: 'var(--on-surface-variant)' }}>Orders Logged</div>
          <div className="display-sm" style={{ margin: '8px 0', fontWeight: 700 }}>{fmtNumber(totalOrders)}</div>
          <div className="body-xs" style={{ color: 'var(--on-surface-variant)' }}>Total visible transaction rows</div>
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
        
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', color: 'var(--on-surface)', fontSize: 14 }}>
          <input
            type="checkbox"
            checked={delayOnly}
            onChange={e => setDelayOnly(e.target.checked)}
            style={{ width: 16, height: 16 }}
          />
          Delays Only
        </label>

        <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', color: 'var(--on-surface)', fontSize: 14 }}>
          <input
            type="checkbox"
            checked={rejectionsOnly}
            onChange={e => setRejectionsOnly(e.target.checked)}
            style={{ width: 16, height: 16 }}
          />
          Rejections Only
        </label>

        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
          <span className="label-caps" style={{ color: 'var(--on-surface-variant)' }}>Show Limit:</span>
          <select
            value={limit}
            onChange={e => setLimit(Number(e.target.value))}
            style={{
              background: 'var(--surface-container)',
              border: '1px solid var(--outline-variant)',
              color: 'var(--on-surface)',
              borderRadius: 6,
              padding: '6px 12px',
              fontSize: 14,
              outline: 'none'
            }}
          >
            {[50, 100, 150, 250, 500].map(val => (
              <option key={val} value={val}>{val} Rows</option>
            ))}
          </select>
        </div>
      </div>

      {/* Transactions Table */}
      <div className="card" style={{ overflow: 'auto' }}>
        <table className="data-table" style={{ minWidth: 1000 }}>
          <thead>
            <tr>
              <th style={{ cursor: 'pointer' }} onClick={() => toggleSort('transaction_id')}>
                ID {sortKey === 'transaction_id' ? (sortDir === -1 ? '↓' : '↑') : ''}
              </th>
              <th style={{ cursor: 'pointer' }} onClick={() => toggleSort('supplier_name')}>
                Supplier Name {sortKey === 'supplier_name' ? (sortDir === -1 ? '↓' : '↑') : ''}
              </th>
              <th style={{ cursor: 'pointer' }} onClick={() => toggleSort('sku')}>
                Product SKU {sortKey === 'sku' ? (sortDir === -1 ? '↓' : '↑') : ''}
              </th>
              <th style={{ cursor: 'pointer' }} onClick={() => toggleSort('order_date')}>
                Order Date {sortKey === 'order_date' ? (sortDir === -1 ? '↓' : '↑') : ''}
              </th>
              <th>Promised Date</th>
              <th>Actual Date</th>
              <th style={{ cursor: 'pointer', textAlign: 'right' }} onClick={() => toggleSort('delayDays')}>
                Delay (Days) {sortKey === 'delayDays' ? (sortDir === -1 ? '↓' : '↑') : ''}
              </th>
              <th style={{ textAlign: 'right' }}>Qty Ordered</th>
              <th style={{ textAlign: 'right' }}>Qty Delivered</th>
              <th style={{ cursor: 'pointer', textAlign: 'right' }} onClick={() => toggleSort('quantity_rejected')}>
                Qty Rejected {sortKey === 'quantity_rejected' ? (sortDir === -1 ? '↓' : '↑') : ''}
              </th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(t => (
              <tr key={t.transaction_id}>
                <td className="data-mono" style={{ color: 'var(--on-surface-variant)' }}>#{t.transaction_id}</td>
                <td><strong style={{ color: 'var(--on-surface)' }}>{t.supplier_name}</strong></td>
                <td><span className="data-mono" style={{ color: 'var(--primary)', fontWeight: 600 }}>{t.sku}</span></td>
                <td className="data-mono" style={{ fontSize: 12 }}>{fmtDate(t.order_date)}</td>
                <td className="data-mono" style={{ fontSize: 12 }}>{fmtDate(t.promised_delivery_date)}</td>
                <td className="data-mono" style={{ fontSize: 12 }}>{fmtDate(t.actual_delivery_date)}</td>
                <td className="data-mono" style={{ textAlign: 'right', fontWeight: t.delayDays > 0 ? 600 : undefined, color: t.delayDays > 5 ? '#ff6b59' : t.delayDays > 0 ? '#ffa600' : 'var(--primary)' }}>
                  {t.delayDays > 0 ? `+${t.delayDays}d` : '0d'}
                </td>
                <td className="data-mono" style={{ textAlign: 'right' }}>{fmtNumber(t.quantity_ordered)}</td>
                <td className="data-mono" style={{ textAlign: 'right' }}>{fmtNumber(t.quantity_delivered)}</td>
                <td className="data-mono" style={{ textAlign: 'right', fontWeight: t.quantity_rejected > 0 ? 600 : undefined, color: t.quantity_rejected > 0 ? '#ff6b59' : 'var(--on-surface-variant)' }}>
                  {t.quantity_rejected > 0 ? `${fmtNumber(t.quantity_rejected)} (${t.rejectionRate.toFixed(1)}%)` : '0'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
