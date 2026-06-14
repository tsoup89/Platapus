import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import {
  Store, TrendingUp, DollarSign, Package, AlertCircle,
  Clock, CheckCircle, ExternalLink, RefreshCw, ShoppingBag,
} from 'lucide-react'
import { getSellDashboard, removeSellListing } from '../api'

function fmtMoney(v) {
  if (v == null) return '—'
  return `$${Number(v).toFixed(2)}`
}

function fmtNum(v) {
  if (v == null) return '—'
  return Number(v).toLocaleString()
}

const PLATFORM_COLOR = { ebay: '#e43137', facebook: '#1877f2' }

function KpiCard({ icon: Icon, label, value, sub, color, onClick }) {
  return (
    <div className={`kpi-card${onClick ? ' kpi-clickable' : ''}`} onClick={onClick}>
      <div className="kpi-icon" style={{ color: color || 'var(--accent)' }}>
        <Icon size={20} />
      </div>
      <div className="kpi-body">
        <div className="kpi-value">{value}</div>
        <div className="kpi-label">{label}</div>
        {sub && <div className="kpi-sub">{sub}</div>}
      </div>
    </div>
  )
}

function PlatformBadge({ platform }) {
  const color = PLATFORM_COLOR[platform] || '#888'
  return (
    <span style={{
      fontSize: 10, fontWeight: 700, borderRadius: 4,
      padding: '2px 7px', background: color + '22', color,
      textTransform: 'uppercase',
    }}>{platform}</span>
  )
}

function StatusDot({ status }) {
  const map = {
    DRAFT:   '#94a3b8',
    POSTING: '#fbbf24',
    POSTED:  '#3b82f6',
    SOLD:    '#22c55e',
    REMOVED: '#94a3b8',
    FAILED:  '#ef4444',
  }
  return (
    <span style={{
      display: 'inline-block', width: 7, height: 7,
      borderRadius: '50%', background: map[status] || '#888',
      flexShrink: 0,
    }} title={status} />
  )
}

export default function SellDashboard() {
  const navigate = useNavigate()
  const qc = useQueryClient()

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['sell-dashboard'],
    queryFn: getSellDashboard,
    refetchInterval: 60_000,
  })

  const removeMut = useMutation({
    mutationFn: (id) => removeSellListing(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['sell-dashboard'] })
    },
  })

  if (isLoading) return <div className="loading">Loading dashboard…</div>

  const d = data || {}
  const inv = d.inventory || {}

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Sell Dashboard</div>
          <div className="page-subtitle">Overview of your active listings and sell-side performance.</div>
        </div>
        <button className="btn btn-secondary" onClick={() => refetch()}>
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {/* KPI row */}
      <div className="kpi-grid">
        <KpiCard
          icon={ShoppingBag}
          label="Active listings"
          value={fmtNum(d.active_listings_count)}
          sub={`${fmtMoney(d.total_listed_value)} total value`}
          color="#3b82f6"
        />
        <KpiCard
          icon={DollarSign}
          label="Profit this month"
          value={fmtMoney(d.profit_this_month)}
          sub={`${fmtNum(d.sold_this_month_count)} item${d.sold_this_month_count === 1 ? '' : 's'} sold · ${fmtMoney(d.revenue_this_month)} revenue`}
          color="var(--green)"
          onClick={() => navigate('/profit')}
        />
        <KpiCard
          icon={TrendingUp}
          label="All-time profit"
          value={fmtMoney(d.total_profit_alltime)}
          sub={`${fmtNum(d.total_sold_alltime)} items sold`}
          color="#f59e0b"
          onClick={() => navigate('/profit')}
        />
        <KpiCard
          icon={Package}
          label="Inventory"
          value={fmtNum((inv.draft || 0) + (inv.listed || 0))}
          sub={`${inv.draft || 0} draft · ${inv.listed || 0} listed · ${inv.sold || 0} sold`}
          color="var(--text-muted)"
          onClick={() => navigate('/inventory')}
        />
      </div>

      <div className="dashboard-cols">
        {/* Needs attention */}
        <div className="dashboard-panel">
          <div className="dashboard-panel-title">
            <AlertCircle size={14} style={{ color: '#f59e0b' }} />
            Needs attention
            {(d.attention?.length > 0) && (
              <span className="dashboard-badge">{d.attention.length}</span>
            )}
          </div>
          {(!d.attention || d.attention.length === 0) ? (
            <div className="dashboard-empty">
              <CheckCircle size={20} style={{ color: 'var(--green)', opacity: 0.6 }} />
              <span>Nothing needs attention right now.</span>
            </div>
          ) : (
            <div className="dashboard-list">
              {d.attention.map((item, i) => (
                <div key={i} className={`attention-row attention-${item.type}`}>
                  <div className="attention-icon">
                    {item.type === 'failed_listing'
                      ? <AlertCircle size={14} style={{ color: '#ef4444' }} />
                      : <Clock size={14} style={{ color: '#f59e0b' }} />
                    }
                  </div>
                  <div className="attention-body">
                    <div className="attention-title">
                      <span
                        className="attention-link"
                        onClick={() => navigate('/inventory')}
                      >{item.title}</span>
                      <PlatformBadge platform={item.platform} />
                    </div>
                    <div className="attention-msg">{item.message}</div>
                  </div>
                  <div className="attention-actions">
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={() => navigate('/inventory')}
                    >View</button>
                    {item.type === 'failed_listing' && (
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => {
                          if (confirm('Remove this failed listing record?')) {
                            removeMut.mutate(item.sell_listing_id)
                          }
                        }}
                      >Dismiss</button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Recent activity */}
        <div className="dashboard-panel">
          <div className="dashboard-panel-title">
            <Clock size={14} />
            Recent activity
          </div>
          {(!d.activity || d.activity.length === 0) ? (
            <div className="dashboard-empty">
              <ShoppingBag size={20} style={{ opacity: 0.3 }} />
              <span>No activity yet. Start listing items from Inventory.</span>
            </div>
          ) : (
            <div className="dashboard-list">
              {d.activity.map((item, i) => (
                <div key={i} className="activity-row">
                  <StatusDot status={item.status} />
                  <div className="activity-body">
                    <span
                      className="attention-link"
                      onClick={() => navigate('/inventory')}
                    >{item.title}</span>
                    <PlatformBadge platform={item.platform} />
                  </div>
                  <div className="activity-right">
                    {item.status === 'SOLD'
                      ? <span style={{ color: 'var(--green)', fontWeight: 600, fontSize: 12 }}>
                          {fmtMoney(item.sale_price)}
                        </span>
                      : <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                          {fmtMoney(item.listed_price)}
                        </span>
                    }
                    <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                      {item.updated_at ? new Date(item.updated_at).toLocaleDateString() : ''}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
