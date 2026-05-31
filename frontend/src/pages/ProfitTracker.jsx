import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { TrendingUp, ExternalLink, DollarSign, Package, BarChart2 } from 'lucide-react'
import { getSellProfit } from '../api'

function fmtMoney(v) {
  if (v == null) return '—'
  const n = Number(v)
  const color = n >= 0 ? 'var(--green)' : '#ef4444'
  return <span style={{ color, fontWeight: 600 }}>${Math.abs(n).toFixed(2)}{n < 0 ? ' loss' : ''}</span>
}

function fmtMoneyPlain(v) {
  if (v == null) return '—'
  return `$${Number(v).toFixed(2)}`
}

function fmtPct(v) {
  if (v == null) return '—'
  const color = v >= 0 ? 'var(--green)' : '#ef4444'
  return <span style={{ color, fontWeight: 600 }}>{v > 0 ? '+' : ''}{v}%</span>
}

const PLATFORM_COLOR = { ebay: '#e43137', facebook: '#1877f2' }
const DAY_OPTIONS = [
  { label: 'All time', value: null },
  { label: 'Last 30 days', value: 30 },
  { label: 'Last 90 days', value: 90 },
  { label: 'Last 365 days', value: 365 },
]

function MiniBar({ value, max, color }) {
  const pct = max > 0 ? Math.max(2, Math.round((value / max) * 100)) : 2
  return (
    <div style={{ height: 6, background: 'var(--border)', borderRadius: 3, flex: 1 }}>
      <div style={{ height: '100%', width: `${pct}%`, background: color, borderRadius: 3 }} />
    </div>
  )
}

// Simple bar chart using divs — no chart library needed
function MonthlyChart({ monthly }) {
  if (!monthly || monthly.length === 0) return (
    <div className="chart-empty">No monthly data yet.</div>
  )

  const maxNet = Math.max(...monthly.map(m => Math.abs(m.net)), 1)

  return (
    <div className="monthly-chart">
      {monthly.map(m => (
        <div key={m.month} className="monthly-bar-col">
          <div className="monthly-bar-wrap">
            <div
              className={`monthly-bar ${m.net >= 0 ? 'monthly-bar-pos' : 'monthly-bar-neg'}`}
              style={{ height: `${Math.max(4, Math.round(Math.abs(m.net) / maxNet * 100))}%` }}
              title={`${m.month}: ${fmtMoneyPlain(m.net)} net (${m.count} sold)`}
            />
          </div>
          <div className="monthly-bar-label">{m.month.slice(5)}</div>
          <div className="monthly-bar-value">{fmtMoneyPlain(m.net)}</div>
        </div>
      ))}
    </div>
  )
}

export default function ProfitTracker() {
  const [days, setDays] = useState(null)
  const [platform, setPlatform] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['sell-profit', days, platform],
    queryFn: () => getSellProfit({
      ...(days ? { days } : {}),
      ...(platform ? { platform } : {}),
    }),
  })

  const rows = data?.rows || []
  const summary = data?.summary || {}
  const byPlatform = data?.by_platform || {}
  const monthly = data?.monthly || []

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Profit Tracker</div>
          <div className="page-subtitle">Every sale, with fees, costs, and net profit.</div>
        </div>
      </div>

      {/* Filters */}
      <div className="profit-filters">
        <div className="btn-group">
          {DAY_OPTIONS.map(opt => (
            <button
              key={opt.label}
              className={`btn btn-secondary btn-sm${days === opt.value && !platform ? ' active' : ''}`}
              onClick={() => setDays(opt.value)}
            >{opt.label}</button>
          ))}
        </div>
        <div className="btn-group">
          {['', 'ebay', 'facebook'].map(p => (
            <button
              key={p}
              className={`btn btn-secondary btn-sm${platform === p ? ' active' : ''}`}
              style={p && platform === p ? { borderColor: PLATFORM_COLOR[p], color: PLATFORM_COLOR[p] } : {}}
              onClick={() => setPlatform(p)}
            >{p ? p.charAt(0).toUpperCase() + p.slice(1) : 'All platforms'}</button>
          ))}
        </div>
      </div>

      {isLoading && <div className="loading">Loading profit data…</div>}

      {!isLoading && (
        <>
          {/* Summary cards */}
          <div className="profit-summary-grid">
            <div className="profit-kpi">
              <div className="profit-kpi-label">Net profit</div>
              <div className="profit-kpi-value">{fmtMoney(summary.total_net)}</div>
            </div>
            <div className="profit-kpi">
              <div className="profit-kpi-label">Revenue</div>
              <div className="profit-kpi-value" style={{ color: 'var(--text-primary)' }}>
                {fmtMoneyPlain(summary.total_revenue)}
              </div>
            </div>
            <div className="profit-kpi">
              <div className="profit-kpi-label">Fees + shipping</div>
              <div className="profit-kpi-value" style={{ color: '#ef4444' }}>
                −{fmtMoneyPlain((summary.total_fees || 0) + (summary.total_shipping || 0))}
              </div>
            </div>
            <div className="profit-kpi">
              <div className="profit-kpi-label">Inventory cost</div>
              <div className="profit-kpi-value" style={{ color: '#ef4444' }}>
                −{fmtMoneyPlain(summary.total_cost)}
              </div>
            </div>
            <div className="profit-kpi">
              <div className="profit-kpi-label">Avg ROI</div>
              <div className="profit-kpi-value">{fmtPct(summary.avg_roi_pct)}</div>
            </div>
            <div className="profit-kpi">
              <div className="profit-kpi-label">Items sold</div>
              <div className="profit-kpi-value" style={{ color: 'var(--text-primary)' }}>
                {summary.count ?? 0}
              </div>
            </div>
          </div>

          {rows.length === 0 ? (
            <div className="empty-state" style={{ marginTop: 32 }}>
              <TrendingUp size={36} style={{ opacity: 0.3, marginBottom: 12 }} />
              <div>No sales yet.</div>
              <div style={{ fontSize: 12, marginTop: 6 }}>
                Mark items as sold from the Inventory page to track profit here.
              </div>
            </div>
          ) : (
            <div className="profit-layout">
              {/* Monthly chart + platform breakdown */}
              <div className="profit-sidebar">
                <div className="profit-panel">
                  <div className="profit-panel-title">
                    <BarChart2 size={13} /> Monthly net profit
                  </div>
                  <MonthlyChart monthly={monthly} />
                </div>

                {Object.keys(byPlatform).length > 0 && (
                  <div className="profit-panel">
                    <div className="profit-panel-title">
                      <Package size={13} /> By platform
                    </div>
                    {Object.entries(byPlatform).map(([p, stats]) => {
                      const maxRev = Math.max(...Object.values(byPlatform).map(s => s.revenue), 1)
                      return (
                        <div key={p} className="platform-row">
                          <div className="platform-row-header">
                            <span style={{
                              fontSize: 11, fontWeight: 700, color: PLATFORM_COLOR[p] || '#888',
                              textTransform: 'uppercase',
                            }}>{p}</span>
                            <span style={{ fontSize: 12, marginLeft: 'auto' }}>
                              {fmtMoneyPlain(stats.net)} net · {stats.count} sold
                            </span>
                          </div>
                          <MiniBar value={stats.revenue} max={maxRev} color={PLATFORM_COLOR[p] || '#888'} />
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>

              {/* Sales table */}
              <div className="profit-table-wrap">
                <table className="profit-table">
                  <thead>
                    <tr>
                      <th>Item</th>
                      <th>Platform</th>
                      <th>Cost</th>
                      <th>Sale</th>
                      <th>Fees</th>
                      <th>Net</th>
                      <th>ROI</th>
                      <th>Sold</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map(r => (
                      <tr key={r.sell_listing_id}>
                        <td>
                          <div className="profit-item-title">
                            {r.platform_url
                              ? <a href={r.platform_url} target="_blank" rel="noreferrer"
                                  style={{ color: 'inherit', textDecoration: 'none' }}>
                                  {r.title} <ExternalLink size={10} style={{ opacity: 0.5 }} />
                                </a>
                              : r.title
                            }
                            {r.category && (
                              <span className="profit-category">{r.category}</span>
                            )}
                          </div>
                        </td>
                        <td>
                          <span style={{
                            fontSize: 10, fontWeight: 700,
                            color: PLATFORM_COLOR[r.platform] || '#888',
                            textTransform: 'uppercase',
                          }}>{r.platform}</span>
                        </td>
                        <td style={{ color: 'var(--text-muted)' }}>{fmtMoneyPlain(r.purchase_price)}</td>
                        <td>{fmtMoneyPlain(r.sale_price)}</td>
                        <td style={{ color: 'var(--text-muted)' }}>
                          {fmtMoneyPlain((r.platform_fees || 0) + (r.shipping_cost || 0))}
                        </td>
                        <td>{fmtMoney(r.net_profit)}</td>
                        <td>{fmtPct(r.roi_pct)}</td>
                        <td style={{ color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                          {r.sold_at ? new Date(r.sold_at).toLocaleDateString() : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
