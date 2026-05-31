import { Routes, Route, NavLink } from 'react-router-dom'
import {
  Activity, List, Database, Settings, Radio, ShoppingBag,
  Package, Store, TrendingUp,
} from 'lucide-react'
import Overview from './pages/Overview'
import ScraperHealth from './pages/ScraperHealth'
import Watchlists from './pages/Watchlists'
import Listings from './pages/Listings'
import PricingTables from './pages/PricingTables'
import SettingsPage from './pages/SettingsPage'
import Inventory from './pages/Inventory'
import SellDashboard from './pages/SellDashboard'
import ProfitTracker from './pages/ProfitTracker'
import './App.css'

const NAV = [
  { kind: 'section', label: 'Buy' },
  { to: '/', icon: Activity, label: 'Overview' },
  { to: '/health', icon: Radio, label: 'Scraper Health' },
  { to: '/watchlists', icon: List, label: 'Watchlists' },
  { to: '/listings', icon: ShoppingBag, label: 'Listings' },
  { to: '/pricing', icon: Database, label: 'Pricing Tables' },
  { kind: 'section', label: 'Sell' },
  { to: '/inventory', icon: Package, label: 'Inventory', sell: true },
  { to: '/sell-dashboard', icon: Store, label: 'Sell Dashboard', sell: true },
  { to: '/profit', icon: TrendingUp, label: 'Profit', sell: true },
  { kind: 'section', label: 'System' },
  { to: '/settings', icon: Settings, label: 'Settings' },
]

export default function App() {
  return (
    <div className="app-shell">
      <nav className="sidebar">
        <div className="logo-area">
          <img src="/icon.png" alt="Platapicker" className="logo-placeholder" />
          <div className="logo-text">
            <span className="logo-name">Platapicker</span>
            <span className="logo-tagline">Deal Command Center</span>
          </div>
        </div>
        <ul className="nav-list">
          {NAV.map((item, idx) => {
            if (item.kind === 'section') {
              return (
                <li key={`section-${idx}`} className="nav-section-label">
                  {item.label}
                </li>
              )
            }
            const { to, icon: Icon, label, sell, disabled } = item
            if (disabled) {
              return (
                <li key={to}>
                  <span
                    className={`nav-link disabled${sell ? ' sell' : ''}`}
                    title="Coming soon"
                  >
                    <Icon size={16} />
                    {label}
                    <span className="nav-soon">soon</span>
                  </span>
                </li>
              )
            }
            return (
              <li key={to}>
                <NavLink
                  to={to}
                  end={to === '/'}
                  className={({ isActive }) =>
                    `nav-link${isActive ? ' active' : ''}${sell ? ' sell' : ''}`
                  }
                >
                  <Icon size={16} />
                  {label}
                </NavLink>
              </li>
            )
          })}
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
          <Route path="/inventory" element={<Inventory />} />
          <Route path="/sell-dashboard" element={<SellDashboard />} />
          <Route path="/profit" element={<ProfitTracker />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </main>
    </div>
  )
}
