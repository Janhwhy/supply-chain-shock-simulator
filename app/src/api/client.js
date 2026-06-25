const BASE_URL = 'http://localhost:8000';

async function apiFetch(path) {
  const res = await fetch(`${BASE_URL}${path}`);
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
  return res.json();
}

export const api = {
  kpis: () => apiFetch('/api/kpis'),
  suppliers: (filters = {}) => {
    const params = new URLSearchParams();
    if (filters.risk_band) params.set('risk_band', filters.risk_band);
    if (filters.priority_quadrant) params.set('priority_quadrant', filters.priority_quadrant);
    return apiFetch(`/api/suppliers${params.toString() ? '?' + params : ''}`);
  },
  supplier: (id) => apiFetch(`/api/suppliers/${id}`),
  scenarios: () => apiFetch('/api/scenarios'),
  simulation: (scenarioId) => apiFetch(`/api/simulation/${scenarioId}`),
  priorityMatrix: () => apiFetch('/api/priority-matrix'),
  playbook: (filters = {}) => {
    const params = new URLSearchParams();
    if (filters.priority_quadrant) params.set('priority_quadrant', filters.priority_quadrant);
    return apiFetch(`/api/playbook${params.toString() ? '?' + params : ''}`);
  },
  graph: () => apiFetch('/api/graph'),
  health: () => apiFetch('/api/health'),
  products: (category) => {
    const params = new URLSearchParams();
    if (category) params.set('category', category);
    return apiFetch(`/api/products${params.toString() ? '?' + params : ''}`);
  },
  relationships: (filters = {}) => {
    const params = new URLSearchParams();
    if (filters.supplier_id) params.set('supplier_id', filters.supplier_id);
    if (filters.product_id) params.set('product_id', filters.product_id);
    return apiFetch(`/api/supply-relationships${params.toString() ? '?' + params : ''}`);
  },
  transactions: (filters = {}) => {
    const params = new URLSearchParams();
    if (filters.supplier_id) params.set('supplier_id', filters.supplier_id);
    if (filters.product_id) params.set('product_id', filters.product_id);
    if (filters.limit) params.set('limit', filters.limit);
    return apiFetch(`/api/transactions${params.toString() ? '?' + params : ''}`);
  },
  criticalSuppliers: () => apiFetch('/api/critical-suppliers'),
  centrality: () => apiFetch('/api/centrality'),
  sensitivity: () => apiFetch('/api/sensitivity'),
};
