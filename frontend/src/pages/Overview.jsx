import { useQuery, useMutation } from '@tanstack/react-query'
import { Play, Send, Activity, Clock } from 'lucide-react'
import { getOverview, runAll, testWebhook, getWebhooks, getSchedulerStatus, runAllNow } from '../api'

const STATUS_BADGE = {
  healthy: <span className="badge badge-green">Healthy</span>,
  warning: <span className="badge badge-yellow">Warning</span>,
  failed: <span className="badge badge-red">Failed</span>,
  needs_login: <span className="badge badge-orange">Needs Login</span>,
  possible_block: <span className="badge badge-orange">Possible Block</span>,
  unknown: <span className="badge badge-gray">Unknown</span>,
}

function fmtDate(dt) {
  if (!dt) return 'Never'
  return new Date(dt + 'Z').toLocaleString()
}

export default function Overview() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['overview'],
    queryFn: getOverview,
    refetchInterval: 30_000,
  })

  const { data: webhooks } = useQuery({ queryKey: ['webhooks'], queryFn: getWebhooks })

  const { data: schedStatus } = useQuery({
    queryKey: ['scheduler-status'],
    queryFn: getSchedulerStatus,
    refetchInterval: 15_000,
  })

  const runMut = useMutation({
    mutationFn: runAllNow,
    onSuccess: () => setTimeout(refetch, 1000),
  })

  const testMut = useMutation({
    mutationFn: () => {
      if (!webhooks?.length) return Promise.reject('No webhooks configured.')
      return testWebhook(webhooks[0].id)
    },
  })

  if (isLoading) return <div className="loading">Loading overview...</div>
  if (error) return <div className="error-box">Failed to load overview: {error.message}</div>

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">🦆 Platapicker</div>
          <div className="page-subtitle">Deal monitoring control center</div>
        </div>
        <div className="actions-row">
          <button
            className="btn btn-primary"
            onClick={() => runMut.mutate()}
            disabled={runMut.isPending}
          >
            <Play size={14} />
            {runMut.isPending ? 'Running...' : 'Run All Now'}
          </button>
          <button
            className="btn btn-secondary"
            onClick={() => testMut.mutate()}
            disabled={testMut.isPending}
          >
            <Send size={14} />
            Test Discord
          </button>
        </div>
      </div>

      {runMut.isSuccess && <div className="success-box">✅ Scrapers queued for run.</div>}
      {runMut.isError && <div className="error-box">❌ {String(runMut.error)}</div>}
      {testMut.isSuccess && <div className="success-box">✅ Test message sent!</div>}
      {testMut.isError && <div className="error-box">❌ {String(testMut.error?.response?.data?.detail || testMut.error)}</div>}

      <div className="stat-grid">
        <div className="stat-card">
          <div className="stat-label">Scrapers Enabled</div>
          <div className="stat-value">{data.scrapers_enabled}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Watchlists Active</div>
          <div className="stat-value">{data.watchlists_enabled}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Alerts Today</div>
          <div className={`stat-value ${data.alerts_today > 0 ? 'green' : ''}`}>{data.alerts_today}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Errors Today</div>
          <div className={`stat-value ${data.errors_today > 0 ? 'red' : ''}`}>{data.errors_today}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Last Run</div>
          <div style={{ fontSize: 14, paddingTop: 6 }}>{fmtDate(data.last_run)}</div>
        </div>
      </div>

      <div className="card">
        <div className="card-title">Scraper Status</div>
        <table>
          <thead>
            <tr>
              <th>Source</th>
              <th>Status</th>
              <th>Last Run</th>
              <th>Last Success</th>
              <th>Last Error</th>
            </tr>
          </thead>
          <tbody>
            {data.sources.map(src => (
              <tr key={src.name}>
                <td style={{ fontWeight: 600 }}>{src.name}</td>
                <td>{STATUS_BADGE[src.status] || <span className="badge badge-gray">{src.status}</span>}</td>
                <td className="text-muted">{fmtDate(src.last_run_at)}</td>
                <td className="text-muted">{fmtDate(src.last_success_at)}</td>
                <td style={{ color: 'var(--red)', fontSize: 12 }}>{src.last_error ? src.last_error.slice(0, 80) : '—'}</td>
              </tr>
            ))}
            {!data.sources.length && (
              <tr><td colSpan={5} className="text-muted" style={{ textAlign: 'center', padding: 24 }}>No sources configured.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <div style={{ marginTop: 16, display: 'flex', gap: 16, alignItems: 'center', fontSize: 12, color: 'var(--text-muted)' }}>
        <span>
          <Activity size={12} style={{ verticalAlign: 'middle', marginRight: 4 }} />
          Refreshes every 30s
        </span>
        {schedStatus && (
          <span>
            <Clock size={12} style={{ verticalAlign: 'middle', marginRight: 4 }} />
            Scheduler: {schedStatus.running ? (
              <span style={{ color: 'var(--green)' }}>
                running — next run {schedStatus.jobs?.[0]?.next_run ? fmtDate(schedStatus.jobs[0].next_run) : '—'}
              </span>
            ) : (
              <span style={{ color: 'var(--text-muted)' }}>disabled (enable in Settings)</span>
            )}
          </span>
        )}
        <span style={{ marginLeft: 'auto', color: 'var(--border)' }}>🦆 logo placeholder</span>
      </div>
    </div>
  )
}
