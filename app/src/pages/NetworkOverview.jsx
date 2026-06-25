import React, { useEffect, useState, useRef } from 'react';
import { api } from '../api/client';
import { LoadingSpinner, ErrorBox } from '../components/LoadingSpinner';

const CRIT_COLORS = ['#464c89', '#4299e1', '#ffa600', '#ff6b59', '#003d5c', '#954e9b', '#8a919c'];

function getNodeColor(node, criticalIds) {
  if (node.type === 'product') return '#003d5c';
  if (criticalIds.has(node.id)) return '#ff6b59';
  return '#464c89';
}

export function NetworkOverview() {
  const [graphData, setGraphData] = useState(null);
  const [centralityData, setCentralityData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [hoveredNode, setHoveredNode] = useState(null);
  const canvasRef = useRef(null);

  useEffect(() => {
    Promise.all([api.graph(), api.centrality()])
      .then(([g, c]) => {
        setGraphData(g);
        setCentralityData(c);
        setLoading(false);
      })
      .catch(e => {
        setError(e.message);
        setLoading(false);
      });
  }, []);

  if (loading) return <LoadingSpinner message="Building dependency graph…" />;
  if (error)   return <ErrorBox message={error} />;

  const nodes = graphData?.nodes || [];
  const edges = graphData?.edges || [];

  // Compute geo concentration from nodes
  const supplierNodes = nodes.filter(n => n.type === 'supplier');
  const geoMap = {};
  supplierNodes.forEach(n => {
    if (n.country) {
      geoMap[n.country] = (geoMap[n.country] || 0) + (n.pagerank_score || 0);
    }
  });
  const totalGeo = Object.values(geoMap).reduce((a, b) => a + b, 0) || 1;
  const geoSorted = Object.entries(geoMap)
    .map(([country, score]) => ({ country, pct: (score / totalGeo) * 100 }))
    .sort((a, b) => b.pct - a.pct)
    .slice(0, 6);

  // Top suppliers by pagerank
  const topSuppliers = [...supplierNodes]
    .sort((a, b) => (b.pagerank_score || 0) - (a.pagerank_score || 0))
    .slice(0, 10);

  const criticalIds = new Set(topSuppliers.slice(0, 2).map(n => n.node_id));

  // Simple force-layout simulation (manual canvas draw)
  const geoColors = ['#464c89', '#003d5c', '#ffa600', '#ff6b59', '#954e9b', '#4299e1'];

  function critBand(score) {
    if (score > 0.8) return { label: 'L1-RED', color: '#ff6b59', text: 'white' };
    if (score > 0.5) return { label: 'L2-ORG', color: '#ffa600', text: 'black' };
    return { label: 'L3-YLW', color: '#464c89', text: 'white' };
  }

  return (
    <>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
        <div>
          <h2 className="headline-lg">Network Dependency Mapping</h2>
          <p className="body-sm" style={{ color: 'var(--on-surface-variant)', marginTop: 4 }}>
            Real-time supply chain topology — {nodes.length} nodes, {edges.length} edges
          </p>
        </div>
        <div style={{ display: 'flex', gap: 12 }}>
          <button style={{ background: 'transparent', border: '1px solid var(--outline-variant)', color: 'var(--on-surface)', fontSize: 12, fontWeight: 700, padding: '8px 24px', borderRadius: 4, letterSpacing: '0.05em', textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: 8 }}>
            <span className="material-symbols-outlined" style={{ fontSize: 16 }}>filter_list</span> Filters
          </button>
          <button
            style={{ background: 'var(--primary-container)', color: 'var(--on-primary-container)', fontSize: 12, fontWeight: 700, padding: '8px 24px', borderRadius: 4, letterSpacing: '0.05em', textTransform: 'uppercase' }}
            onClick={() => {
              const rows = [['node_id','type','name','country','tier','pagerank_score']];
              nodes.forEach(n => rows.push([n.node_id, n.type, n.name, n.country||'', n.tier||'', (n.pagerank_score||0).toFixed(4)]));
              const csv = rows.map(r => r.join(',')).join('\n');
              const a = document.createElement('a'); a.href = 'data:text/csv;charset=utf-8,' + encodeURIComponent(csv); a.download = 'network_graph.csv'; a.click();
            }}
          >Export Data</button>
        </div>
      </div>

      <div className="network-grid">
        {/* Graph Panel */}
        <div className="network-graph-panel">
          <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--outline-variant)', background: 'var(--surface-container-low)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h2 className="title-md">Topology Visualization</h2>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
              {[['#ff6b59','Critical'],['#464c89','Standard'],['#003d5c','Product']].map(([color, label]) => (
                <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <div style={{ width: 8, height: 8, borderRadius: '50%', background: color }} />
                  <span className="label-caps" style={{ color: 'var(--on-surface-variant)' }}>{label}</span>
                </div>
              ))}
            </div>
          </div>
          {/* Interactive SVG graph (simplified force layout) */}
          <NetworkGraph nodes={nodes} edges={edges} criticalIds={criticalIds} />
        </div>

        {/* Right Panel */}
        <div className="network-right-panel">
          {/* Geographic Concentration */}
          <div className="card card--p" style={{ flexShrink: 0 }}>
            <h2 className="title-md" style={{ marginBottom: 8 }}>Geographic Concentration</h2>
            <p className="body-sm" style={{ color: 'var(--on-surface-variant)', marginBottom: 16 }}>Total PageRank Weight by Country</p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {geoSorted.map(({ country, pct }, i) => (
                <div key={country} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span className="label-caps">{country}</span>
                    <span className="data-mono" style={{ color: geoColors[i % geoColors.length] }}>{pct.toFixed(1)}%</span>
                  </div>
                  <div className="geo-bar-track">
                    <div className="geo-bar-fill" style={{ width: `${pct}%`, background: geoColors[i % geoColors.length] }} />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Critical Suppliers Table */}
          <div className="card" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--outline-variant)', background: 'var(--surface-container-low)', flexShrink: 0 }}>
              <h2 className="title-md">Critical Suppliers</h2>
              <p className="body-sm" style={{ color: 'var(--on-surface-variant)' }}>Top entities by network centrality</p>
            </div>
            <div style={{ overflowY: 'auto', flex: 1 }}>
              <table className="data-table">
                <thead style={{ position: 'sticky', top: 0, background: 'var(--surface-container-low)', zIndex: 1 }}>
                  <tr>
                    <th>Rank</th>
                    <th>Supplier</th>
                    <th>Score</th>
                    <th style={{ textAlign: 'right' }}>Crit Band</th>
                  </tr>
                </thead>
                <tbody>
                  {topSuppliers.map((n, i) => {
                    const band = critBand(n.pagerank_score);
                    return (
                      <tr key={n.node_id}>
                        <td className="data-mono" style={{ color: 'var(--outline)' }}>{String(i + 1).padStart(2, '0')}</td>
                        <td style={{ fontWeight: 500 }}>{n.name}</td>
                        <td className="data-mono">{(n.pagerank_score || 0).toFixed(3)}</td>
                        <td style={{ textAlign: 'right' }}>
                          <span style={{ display: 'inline-block', padding: '2px 8px', borderRadius: '100px', background: band.color, color: band.text, fontSize: 12, fontWeight: 700, letterSpacing: '0.05em' }}>
                            {band.label}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      {/* Centrality Metrics Table */}
      <div className="card card--p" style={{ marginTop: 24 }}>
        <div style={{ paddingBottom: 16, borderBottom: '1px solid var(--outline-variant)', marginBottom: 16 }}>
          <h3 className="title-md">Supplier Network Centrality Breakdown</h3>
          <p className="body-sm" style={{ color: 'var(--on-surface-variant)', marginTop: 4 }}>
            Detailed structural centrality metrics. Degree measures immediate connections, Betweenness measures control over paths, and Closeness measures speed of access.
          </p>
        </div>
        <div style={{ overflowX: 'auto' }}>
          <table className="data-table" style={{ minWidth: 800 }}>
            <thead>
              <tr>
                <th>Supplier Name</th>
                <th style={{ textAlign: 'right' }}>Degree Centrality</th>
                <th style={{ textAlign: 'right' }}>Betweenness Centrality</th>
                <th style={{ textAlign: 'right' }}>Closeness Centrality</th>
              </tr>
            </thead>
            <tbody>
              {centralityData.slice(0, 15).map((c) => {
                // Max values for scaling
                const maxDeg = Math.max(...centralityData.map(d => d.degree_centrality || 1e-5), 1e-5);
                const maxBet = Math.max(...centralityData.map(d => d.betweenness_centrality || 1e-5), 1e-5);
                const maxClo = Math.max(...centralityData.map(d => d.closeness_centrality || 1e-5), 1e-5);
                
                const degPct = ((c.degree_centrality || 0) / maxDeg) * 100;
                const betPct = ((c.betweenness_centrality || 0) / maxBet) * 100;
                const cloPct = ((c.closeness_centrality || 0) / maxClo) * 100;

                return (
                  <tr key={c.supplier_id}>
                    <td><strong style={{ color: 'var(--on-surface)' }}>{c.supplier_name}</strong></td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'flex-end' }}>
                        <span className="data-mono">{(c.degree_centrality || 0).toFixed(4)}</span>
                        <div style={{ width: 60, background: 'var(--surface-container-high)', height: 6, borderRadius: 3, overflow: 'hidden' }}>
                          <div style={{ width: `${degPct}%`, background: 'var(--primary)', height: '100%' }} />
                        </div>
                      </div>
                    </td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'flex-end' }}>
                        <span className="data-mono">{(c.betweenness_centrality || 0).toFixed(4)}</span>
                        <div style={{ width: 60, background: 'var(--surface-container-high)', height: 6, borderRadius: 3, overflow: 'hidden' }}>
                          <div style={{ width: `${betPct}%`, background: '#ff6b59', height: '100%' }} />
                        </div>
                      </div>
                    </td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'flex-end' }}>
                        <span className="data-mono">{(c.closeness_centrality || 0).toFixed(4)}</span>
                        <div style={{ width: 60, background: 'var(--surface-container-high)', height: 6, borderRadius: 3, overflow: 'hidden' }}>
                          <div style={{ width: `${cloPct}%`, background: '#ffa600', height: '100%' }} />
                        </div>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

/** Simple D3-style SVG force graph */
function NetworkGraph({ nodes, edges, criticalIds }) {
  const [positions, setPositions] = useState({});
  const svgRef = useRef(null);
  const [dims, setDims] = useState({ w: 600, h: 400 });

  useEffect(() => {
    if (!svgRef.current) return;
    const ro = new ResizeObserver(entries => {
      for (const entry of entries) {
        setDims({ w: entry.contentRect.width, h: entry.contentRect.height });
      }
    });
    ro.observe(svgRef.current.parentElement);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    if (!nodes.length) return;
    
    const cx = dims.w / 2;
    const cy = dims.h / 2;
    
    // 1. Initialize random positions near the center with some jitter
    let pos = {};
    nodes.forEach(n => {
      pos[n.node_id] = {
        x: cx + (Math.random() - 0.5) * (dims.w * 0.3),
        y: cy + (Math.random() - 0.5) * (dims.h * 0.3)
      };
    });

    // Sort edges by weight to get the primary structural skeleton
    const topEdges = [...edges].sort((a, b) => b.weight - a.weight).slice(0, 50);

    // 2. Run force-directed physics simulation steps
    const iterations = 150;
    const k = Math.sqrt((dims.w * dims.h) / (nodes.length || 1)) * 0.65; // optimal distance
    
    const c_rep = k * k * 0.85; // repulsion constant
    const c_att = 0.04;        // attraction constant
    const c_grav = 0.05;       // gravity constant pulling to center
    const damp = 0.80;         // damping factor

    let currentPos = { ...pos };
    
    for (let step = 0; step < iterations; step++) {
      let forces = {};
      nodes.forEach(n => { forces[n.node_id] = { fx: 0, fy: 0 }; });

      // Repulsion between all nodes (prevent overlapping)
      for (let i = 0; i < nodes.length; i++) {
        const u = nodes[i].node_id;
        const posU = currentPos[u];
        for (let j = i + 1; j < nodes.length; j++) {
          const v = nodes[j].node_id;
          const posV = currentPos[v];
          if (!posU || !posV) continue;
          
          const dx = posU.x - posV.x;
          const dy = posU.y - posV.y;
          const distSq = dx * dx + dy * dy + 1e-4;
          const dist = Math.sqrt(distSq);
          
          if (dist < 220) { // repulsion range
            const f = c_rep / distSq;
            const fx = (dx / dist) * f;
            const fy = (dy / dist) * f;
            
            forces[u].fx += fx;
            forces[u].fy += fy;
            forces[v].fx -= fx;
            forces[v].fy -= fy;
          }
        }
      }

      // Attraction along connected edges
      topEdges.forEach(e => {
        const u = e.source;
        const v = e.target;
        const posU = currentPos[u];
        const posV = currentPos[v];
        if (!posU || !posV) return;

        const dx = posU.x - posV.x;
        const dy = posU.y - posV.y;
        const dist = Math.sqrt(dx * dx + dy * dy) + 1e-4;
        
        // Spring pull
        const f = c_att * (dist - k);
        const fx = (dx / dist) * f;
        const fy = (dy / dist) * f;
        
        forces[u].fx -= fx;
        forces[u].fy -= fy;
        forces[v].fx += fx;
        forces[v].fy += fy;
      });

      // Gravity force pulling towards the canvas center
      nodes.forEach(n => {
        const u = n.node_id;
        const posU = currentPos[u];
        if (!posU) return;
        const dx = cx - posU.x;
        const dy = cy - posU.y;
        
        forces[u].fx += dx * c_grav;
        forces[u].fy += dy * c_grav;
      });

      // Update positions with a speed limit (damping)
      nodes.forEach(n => {
        const u = n.node_id;
        const force = forces[u];
        if (!force || !currentPos[u]) return;
        
        const moveLimit = 15;
        let mx = force.fx * damp;
        let my = force.fy * damp;
        
        const moveDist = Math.sqrt(mx * mx + my * my);
        if (moveDist > moveLimit) {
          mx = (mx / moveDist) * moveLimit;
          my = (my / moveDist) * moveLimit;
        }

        currentPos[u].x += mx;
        currentPos[u].y += my;

        // Keep inside svg boundaries
        currentPos[u].x = Math.max(30, Math.min(dims.w - 30, currentPos[u].x));
        currentPos[u].y = Math.max(30, Math.min(dims.h - 30, currentPos[u].y));
      });
    }

    setPositions(currentPos);
  }, [nodes, edges, dims]);

  const supplierNodes = nodes.filter(n => n.type === 'supplier');
  const productNodes  = nodes.filter(n => n.type === 'product');

  // Only render top-30 edges by weight for clarity
  const visibleEdges = [...edges].sort((a, b) => b.weight - a.weight).slice(0, 40);

  return (
    <div style={{ flex: 1, overflow: 'hidden', position: 'relative' }} ref={svgRef}>
      <svg width="100%" height="100%" style={{ display: 'block' }}>
        <defs>
          <filter id="glow-red">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
          </filter>
        </defs>
        {/* Edges */}
        {visibleEdges.map((e, i) => {
          const s = positions[e.source], t = positions[e.target];
          if (!s || !t) return null;
          return (
            <line key={i} x1={s.x} y1={s.y} x2={t.x} y2={t.y}
              stroke="#404751" strokeWidth={Math.max(0.5, e.weight * 3)} strokeOpacity={0.5} />
          );
        })}
        {/* Product nodes */}
        {productNodes.map(n => {
          const p = positions[n.node_id];
          if (!p) return null;
          return <circle key={n.node_id} cx={p.x} cy={p.y} r={5} fill="#003d5c" opacity={0.7}><title>{n.name}</title></circle>;
        })}
        {/* Supplier nodes */}
        {supplierNodes.map(n => {
          const p = positions[n.node_id];
          if (!p) return null;
          const isCrit = criticalIds.has(n.node_id);
          const r = 6 + (n.pagerank_score || 0) * 20;
          const color = isCrit ? '#ff6b59' : '#464c89';
          return (
            <circle key={n.node_id} cx={p.x} cy={p.y} r={r}
              fill={color} filter={isCrit ? 'url(#glow-red)' : undefined} opacity={0.9}
              style={{ cursor: 'pointer' }}>
              <title>{n.name} (PageRank: {(n.pagerank_score||0).toFixed(3)})</title>
            </circle>
          );
        })}
      </svg>
      {/* Zoom controls */}
      <div style={{ position: 'absolute', bottom: 16, right: 16, background: 'rgba(36,49,70,0.6)', backdropFilter: 'blur(12px)', border: '1px solid var(--outline-variant)', borderRadius: 4, display: 'flex', flexDirection: 'column' }}>
        {['zoom_in','zoom_out','center_focus_strong'].map(icon => (
          <button key={icon} style={{ width: 32, height: 32, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--on-surface)', borderTop: icon !== 'zoom_in' ? '1px solid var(--outline-variant)' : 'none' }}>
            <span className="material-symbols-outlined" style={{ fontSize: 18 }}>{icon}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
