import { Routes, Route, NavLink } from 'react-router-dom'
import { Activity, List, Database, Settings, Radio, ShoppingBag } from 'lucide-react'
import Overview from './pages/Overview'
import ScraperHealth from './pages/ScraperHealth'
import Watchlists from './pages/Watchlists'
import Listings from './pages/Listings'
import PricingTables from './pages/PricingTables'
import SettingsPage from './pages/SettingsPage'
import './App.css'

const NAV = [
  { to: '/', icon: Activity, label: 'Overview' },
  { to: '/health', icon: Radio, label: 'Scraper Health' },
  { to: '/watchlists', icon: List, label: 'Watchlists' },
  { to: '/listings', icon: ShoppingBag, label: 'Listings' },
  { to: '/pricing', icon: Database, label: 'Pricing Tables' },
  { to: '/settings', icon: Settings, label: 'Settings' },
]

export default function App() {
  return (
    <div className="app-shell">
      <nav className="sidebar">
        <div className="logo-area">
          <div className="logo-placeholder">🦆</div>
          <div className="logo-text">
            <span className="logo-name">Platapicker</span>
            <span className="logo-tagline">Deal Command Center</span>
          </div>
        </div>
        <ul className="nav-list">
          {NAV.map(({ to, icon: Icon, label }) => (
            <li key={to}>
              <NavLink
                to={to}
                end={to === '/'}
                className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
              >
                <Icon size={16} />
                {label}
              </NavLink>
            </li>
          ))}
        </ul>
        <div className="sidebar-footer">v1.0.0</div>
      </nav>
      <main className="content">
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/health" element={<ScraperHealth />} />
          <Route path="/watchlists" element={<Watchlists />} />
          <Route path="/listings" element={<Listings />} />
          <Route path="/pricing" element={<PricingTables />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </main>
    </div>
  )
}
