import React, { useEffect, useState, useRef, useCallback } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { api } from '../api/client';
import { LoadingSpinner, ErrorBox } from '../components/LoadingSpinner';


export function NetworkOverview() {
  const [graphData, setGraphData] = useState(null);
  const [centralityData, setCentralityData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

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
    if (score > 0.8) return { label: 'Critical', color: '#ff6b59', text: 'white' };
    if (score > 0.5) return { label: 'High', color: '#ffa600', text: 'black' };
    return { label: 'Standard', color: '#464c89', text: 'white' };
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

/** Force-directed graph using react-force-graph-2d */
function NetworkGraph({ nodes, edges, criticalIds }) {
  const fgRef = useRef();
  const containerRef = useRef();
  const [dims, setDims] = useState({ w: 600, h: 480 });
  const [tooltip, setTooltip] = useState(null); // { node, x, y }

  // Track container size
  useEffect(() => {
    if (!containerRef.current) return;
    const ro = new ResizeObserver(entries => {
      for (const e of entries) {
        setDims({ w: e.contentRect.width, h: e.contentRect.height });
      }
    });
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  // Zoom to fit after initial layout settles
  useEffect(() => {
    if (!fgRef.current) return;
    const t = setTimeout(() => fgRef.current.zoomToFit(400, 40), 800);
    return () => clearTimeout(t);
  }, [nodes, edges]);

  // Build graph data — react-force-graph-2d uses { nodes, links }
  // and requires an `id` field on nodes and `source`/`target` on links
  const graphData = {
    nodes: nodes.map(n => ({
      id: n.node_id,
      name: n.name,
      type: n.type,
      country: n.country,
      tier: n.tier,
      pagerank: n.pagerank_score || 0,
      isCritical: criticalIds.has(n.node_id),
    })),
    links: edges.map(e => ({
      source: e.source,
      target: e.target,
      weight: e.weight || 0.5,
    })),
  };

  // Node appearance
  const nodeCanvasObject = useCallback((node, ctx, globalScale) => {
    const isCritical = node.isCritical;
    const isProduct = node.type === 'product';
    const r = isProduct ? 4 : Math.max(4, 4 + node.pagerank * 160);
    const color = isProduct ? '#003d5c' : isCritical ? '#ff6b59' : '#464c89';

    // Glow for critical nodes
    if (isCritical) {
      ctx.shadowColor = '#ff6b59';
      ctx.shadowBlur = 12;
    }

    ctx.beginPath();
    ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
    ctx.fillStyle = color;
    ctx.globalAlpha = isProduct ? 0.75 : 0.95;
    ctx.fill();
    ctx.globalAlpha = 1;
    ctx.shadowBlur = 0;

    // Label for critical nodes or when zoomed in enough
    if (isCritical || globalScale > 2.5) {
      ctx.font = `${Math.max(4, 10 / globalScale)}px Inter, sans-serif`;
      ctx.fillStyle = '#e2e8f0';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(node.name?.split(' ')[0] || '', node.x, node.y + r + 6 / globalScale);
    }
  }, []);

  const nodeRelSize = 1;

  const handleNodeHover = useCallback((node, prevNode) => {
    if (node) {
      setTooltip({ node });
    } else {
      setTooltip(null);
    }
  }, []);

  const handleNodeClick = useCallback((node) => {
    // Zoom in on clicked node
    fgRef.current.centerAt(node.x, node.y, 600);
    fgRef.current.zoom(4, 600);
  }, []);

  return (
    <div ref={containerRef} style={{ flex: 1, overflow: 'hidden', position: 'relative', background: 'var(--surface-container-low)' }}>
      <ForceGraph2D
        ref={fgRef}
        width={dims.w}
        height={dims.h}
        graphData={graphData}
        backgroundColor="transparent"
        nodeCanvasObject={nodeCanvasObject}
        nodeRelSize={nodeRelSize}
        nodePointerAreaPaint={(node, color, ctx) => {
          const r = node.type === 'product' ? 4 : Math.max(4, 4 + node.pagerank * 160);
          ctx.beginPath();
          ctx.arc(node.x, node.y, r + 3, 0, 2 * Math.PI);
          ctx.fillStyle = color;
          ctx.fill();
        }}
        linkColor={() => 'rgba(100, 116, 139, 0.35)'}
        linkWidth={link => Math.max(0.4, link.weight * 2.5)}
        linkDirectionalParticles={2}
        linkDirectionalParticleWidth={link => Math.max(0.5, link.weight * 2)}
        linkDirectionalParticleColor={() => 'rgba(70, 76, 137, 0.6)'}
        onNodeHover={handleNodeHover}
        onNodeClick={handleNodeClick}
        enableNodeDrag={true}
        enableZoomInteraction={true}
        enablePanInteraction={true}
        cooldownTicks={120}
        d3AlphaDecay={0.02}
        d3VelocityDecay={0.3}
      />

      {/* Hover tooltip */}
      {tooltip && (
        <div style={{
          position: 'absolute',
          top: 16,
          left: 16,
          background: 'rgba(16, 20, 24, 0.92)',
          backdropFilter: 'blur(12px)',
          border: '1px solid var(--outline-variant)',
          borderRadius: 8,
          padding: '10px 14px',
          pointerEvents: 'none',
          zIndex: 10,
          minWidth: 180,
        }}>
          <div style={{ fontWeight: 700, fontSize: 13, color: tooltip.node.isCritical ? '#ff6b59' : 'var(--on-surface)', marginBottom: 6 }}>
            {tooltip.node.name}
          </div>
          {[
            ['Type', tooltip.node.type === 'product' ? 'Product' : 'Supplier'],
            ...(tooltip.node.type === 'supplier' ? [
              ['Country', tooltip.node.country || '—'],
              ['Tier', tooltip.node.tier != null ? `Tier ${tooltip.node.tier}` : '—'],
              ['Dependency Score', tooltip.node.pagerank.toFixed(4)],
            ] : []),
          ].map(([label, val]) => (
            <div key={label} style={{ display: 'flex', justifyContent: 'space-between', gap: 16, fontSize: 12 }}>
              <span style={{ color: 'var(--on-surface-variant)' }}>{label}</span>
              <span className="data-mono" style={{ color: 'var(--on-surface)' }}>{val}</span>
            </div>
          ))}
        </div>
      )}

      {/* Controls */}
      <div style={{
        position: 'absolute', bottom: 16, right: 16,
        background: 'rgba(36,49,70,0.75)',
        backdropFilter: 'blur(12px)',
        border: '1px solid var(--outline-variant)',
        borderRadius: 6,
        display: 'flex', flexDirection: 'column',
        overflow: 'hidden',
      }}>
        {[
          { icon: 'zoom_in',             action: () => fgRef.current.zoom(fgRef.current.zoom() * 1.4, 200) },
          { icon: 'zoom_out',            action: () => fgRef.current.zoom(fgRef.current.zoom() * 0.7, 200) },
          { icon: 'center_focus_strong', action: () => fgRef.current.zoomToFit(400, 40) },
        ].map(({ icon, action }, i) => (
          <button
            key={icon}
            onClick={action}
            style={{
              width: 34, height: 34,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: 'var(--on-surface)',
              borderTop: i !== 0 ? '1px solid var(--outline-variant)' : 'none',
            }}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 18 }}>{icon}</span>
          </button>
        ))}
      </div>

      {/* Interaction hint */}
      <div style={{
        position: 'absolute', bottom: 16, left: 16,
        fontSize: 11, color: 'var(--on-surface-variant)',
        background: 'rgba(16,20,24,0.6)',
        padding: '4px 10px', borderRadius: 4,
        backdropFilter: 'blur(8px)',
      }}>
        Drag nodes · Scroll to zoom · Click to focus
      </div>
    </div>
  );
}
