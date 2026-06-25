export function LoadingSpinner({ message = 'Loading data…' }) {
  return (
    <div className="loading-container">
      <div className="spinner" />
      <span className="body-sm" style={{ color: 'var(--on-surface-variant)' }}>{message}</span>
    </div>
  );
}

export function ErrorBox({ message }) {
  return (
    <div className="error-box">
      <span className="material-symbols-outlined" style={{ verticalAlign: 'middle', marginRight: 8 }}>error</span>
      {message}
    </div>
  );
}

export function useApi(fetcher, deps = []) {
  const [data, setData] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState(null);

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetcher()
      .then(d => { if (!cancelled) { setData(d); setLoading(false); } })
      .catch(e => { if (!cancelled) { setError(e.message); setLoading(false); } });
    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, loading, error };
}

import React from 'react';
