import { NavLink, useNavigate, useLocation } from 'react-router-dom';
import { useState, useEffect } from 'react';

const NAV_LINKS = [
  { to: '/', icon: 'dashboard', label: 'Overview' },
  { to: '/network', icon: 'hub', label: 'Network Graph' },
  { to: '/suppliers', icon: 'security', label: 'Supplier Risk' },
  { to: '/scenarios', icon: 'local_shipping', label: 'Scenarios' },
  { to: '/playbook', icon: 'assessment', label: 'Playbook' },
  { to: '/products', icon: 'inventory_2', label: 'Products Catalog' },
  { to: '/relationships', icon: 'alt_route', label: 'Relationships' },
  { to: '/transactions', icon: 'receipt_long', label: 'Transactions' },
];

function getPageTitle(pathname) {
  const match = NAV_LINKS.find(({ to }) => to === '/' ? pathname === '/' : pathname.startsWith(to));
  if (match) return match.label;
  if (pathname.startsWith('/suppliers/')) return 'Supplier Detail';
  return 'ShockProof';
}

export function Layout({ children, onToast }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'dark');

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  function handleComingSoon(e) {
    e.preventDefault();
    onToast?.('This feature is coming soon');
  }

  function toggleTheme() {
    setTheme(t => t === 'dark' ? 'light' : 'dark');
  }

  return (
    <div className="app-shell">
      {/* ── Side Nav ── */}
      <nav className="side-nav">
        <div className="side-nav__brand">
          <div className="side-nav__brand-row">
            <span className="side-nav__title">ShockProof</span>
          </div>
          <div className="side-nav__subtitle">Supply Chain Risk Analytics</div>
        </div>

        <div className="side-nav__links">
          {NAV_LINKS.map(({ to, icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) => `side-nav__link${isActive ? ' active' : ''}`}
            >
              <span className={`icon material-symbols-outlined`}>{icon}</span>
              <span>{label}</span>
            </NavLink>
          ))}
        </div>

        <div className="side-nav__footer">
          <a className="side-nav__link" href="#help" onClick={handleComingSoon}>
            <span className="icon material-symbols-outlined">help</span>
            <span>Help Center</span>
          </a>
          <a className="side-nav__link" href="#logout" onClick={handleComingSoon}>
            <span className="icon material-symbols-outlined">logout</span>
            <span>Logout</span>
          </a>
        </div>
      </nav>

      {/* ── Main ── */}
      <div className="main-content">
        <header className="top-bar">
          <span className="top-bar__title">{getPageTitle(location.pathname)}</span>
          <div className="top-bar__actions">
            <button className="top-bar__icon-btn" onClick={toggleTheme} title={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} Mode`}>
              {theme === 'dark' ? 'light_mode' : 'dark_mode'}
            </button>
            <button className="top-bar__icon-btn" onClick={() => onToast?.('No new notifications')}>notifications</button>
            <button className="top-bar__icon-btn" onClick={() => onToast?.('Settings coming soon')}>settings</button>
            <div className="top-bar__avatar material-symbols-outlined">person</div>
          </div>
        </header>

        <div className="page-scroll">{children}</div>
      </div>
    </div>
  );
}
