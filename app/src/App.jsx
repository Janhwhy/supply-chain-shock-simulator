import React, { useState, useCallback } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from './components/Layout';
import { ExecutiveDashboard } from './pages/ExecutiveDashboard';
import { NetworkOverview } from './pages/NetworkOverview';
import { SupplierRisk } from './pages/SupplierRisk';
import { SupplierDetail } from './pages/SupplierDetail';
import { ScenarioAnalysis } from './pages/ScenarioAnalysis';
import { MitigationPlaybook } from './pages/MitigationPlaybook';
import { Products } from './pages/Products';
import { Relationships } from './pages/Relationships';
import { Transactions } from './pages/Transactions';

function Toast({ messages, onRemove }) {
  return (
    <div className="toast-container">
      {messages.map(({ id, text }) => (
        <div key={id} className="toast" onClick={() => onRemove(id)}>{text}</div>
      ))}
    </div>
  );
}

export default function App() {
  const [toasts, setToasts] = useState([]);

  const addToast = useCallback((text) => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, text }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 3500);
  }, []);

  const removeToast = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  return (
    <BrowserRouter>
      <Layout onToast={addToast}>
        <Routes>
          <Route path="/"           element={<ExecutiveDashboard />} />
          <Route path="/network"    element={<NetworkOverview />} />
          <Route path="/suppliers"  element={<SupplierRisk />} />
          <Route path="/suppliers/:id" element={<SupplierDetail />} />
          <Route path="/scenarios"  element={<ScenarioAnalysis />} />
          <Route path="/playbook"   element={<MitigationPlaybook />} />
          <Route path="/products"   element={<Products />} />
          <Route path="/relationships" element={<Relationships />} />
          <Route path="/transactions" element={<Transactions />} />
          <Route path="*"           element={<Navigate to="/" replace />} />
        </Routes>
      </Layout>
      <Toast messages={toasts} onRemove={removeToast} />
    </BrowserRouter>
  );
}
