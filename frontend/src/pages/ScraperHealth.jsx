import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Play, ToggleLeft, ToggleRight, ChevronDown, ChevronUp } from 'lucide-react'
import { getSources, getSourceRuns, triggerRun, toggleSource } from '../api'

const LABELS = { facebook: 'Facebook', mercari: 'Mercari' }

function LoginButton({ sourceName }) {
  const [status, setStatus] = useState('idle') // idle | opening | done | error

  const handleLogin = async () => {
    setStatus('opening')
    try {
      const res = await fetch(`/api/sources/${sourceName}/login`, { method: 'POST' })
      if (!res.ok) throw new Error(`Login request failed (${res.status})`)
      setStatus('done')
      setTimeout(() => setStatus('idle'), 8000)
    } catch {
      setStatus('error')
      setTimeout(() => setStatus('idle'), 4000)
    }
  }

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 12,
      background: 'rgba(255,149,0,0.08)', border: '1px solid rgba(255,149,0,0.25)',
      borderRadius: 8, padding: '10px 14px', marginBottom: 8,
    }}>
      <span>🔑</span>
      <div style={{ flex: 1, fontSize: 13 }}>
        {status === 'done'
          ? `✅ ${LABELS[sourceName]} login window opened — sign in, then close the browser. Your session is saved automatically.`
          : status === 'error'
          ? '❌ Failed to open login window. Is the backend running?'
          : `Log into ${LABELS[sourceName]} once so the scraper can run silently in the background.`
        }
      </div>
      <button
        className="btn btn-sm btn-primary"
        onClick={handleLogin}
        disabled={status === 'opening' || status === 'done'}
        style={{ whiteSpace: 'nowrap' }}
      >
        {status === 'opening' ? 'Opening…' : status === 'done' ? 'Opened ✓' : `Log into ${LABELS[sourceName]}`}
      </button>
    </div>
  )
}

const STATUS_BADGE = {
  healthy: <span className="badge badge-green">Healthy</span>,
  warning: <span className="badge badge-yellow">Warning</span>,
  failed: <span className="badge badge-red">Failed</span>,
  needs_login: <span className="badge badge-orange">Needs Login</span>,
  possible_block: <span className="badge badge-orange">Possible Block / Rate Limit</span>,
  unknown: <span className="badge badge-gray">Unknown</span>,
}

function fmtDate(dt) {
  if (!dt) return 'Never'
  return new Date(dt + 'Z').toLocaleString()
}

function SourceRow({ source }) {
  const [expanded, setExpanded] = useState(false)
  const qc = useQueryClient()

  const { data: runs } = useQuery({
    queryKey: ['runs', source.name],
    queryFn: () => getSourceRuns(source.name, 10),
    enabled: expanded,
  })

  const toggleMut = useMutation({
    mutationFn: () => toggleSource(source.name),
    onSuccess: () => qc.invalidateQueries(['sources']),
  })

  const runMut = useMutation({
    mutationFn: () => triggerRun(source.name),
    onSuccess: () => {
      setTimeout(() => qc.invalidateQueries(['sources']), 3000)
    },
  })

  return (
    <>
      <tr>
        <td>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <button className="btn btn-sm btn-secondary" onClick={() => toggleMut.mutate()} title="Toggle">
              {source.enabled ? <ToggleRight size={14} color="var(--green)" /> : <ToggleLeft size={14} />}
            </button>
            <strong>{source.name}</strong>
          </div>
        </td>
        <td>{STATUS_BADGE[source.status] || source.status}</td>
        <td className="text-muted">{fmtDate(source.last_run_at)}</td>
        <td className="text-muted">{fmtDate(source.last_success_at)}</td>
        <td style={{ color: 'var(--red)', fontSize: 12, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {source.last_error || '—'}
        </td>
        <td>
          <div className="actions-row">
            <button
              className="btn btn-sm btn-primary"
              onClick={() => runMut.mutate()}
              disabled={runMut.isPending}
            >
              <Play size={12} />
              {runMut.isPending ? '...' : 'Run Test'}
            </button>
            <button
              className="btn btn-sm btn-secondary"
              onClick={() => setExpanded(e => !e)}
            >
              {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              Logs
            </button>
          </div>
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={6} style={{ background: 'var(--bg)', padding: '0 0 0 32px' }}>
            <div style={{ padding: '12px 0' }}>
              {(source.name === 'facebook' || source.name === 'mercari') && (
                <LoginButton sourceName={source.name} />
              )}
              <div className="card-title">Recent Runs</div>
              {!runs ? <div className="text-muted">Loading...</div> : (
                <table>
                  <thead>
                    <tr>
                      <th>Started</th>
                      <th>Status</th>
                      <th>Raw</th>
                      <th>Parsed</th>
                      <th>Dupes</th>
                      <th>Alerts</th>
                      <th>Error</th>
                    </tr>
                  </thead>
                  <tbody>
                    {runs.map(r => (
                      <tr key={r.id}>
                        <td className="text-muted">{fmtDate(r.started_at)}</td>
                        <td>
                          <span className={`badge badge-${r.status === 'success' ? 'green' : r.status === 'failed' ? 'red' : 'yellow'}`}>
                            {r.status}
                          </span>
                        </td>
                        <td>{r.raw_count}</td>
                        <td>{r.parsed_count}</td>
                        <td>{r.duplicate_count}</td>
                        <td>{r.alert_count}</td>
                        <td style={{ color: 'var(--red)', fontSize: 12 }}>{r.error_message?.slice(0, 60) || '—'}</td>
                      </tr>
                    ))}
                    {!runs.length && (
                      <tr><td colSpan={7} className="text-muted" style={{ textAlign: 'center', padding: 16 }}>No runs yet.</td></tr>
                    )}
                  </tbody>
                </table>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

export default function ScraperHealth() {
  const { data: sources, isLoading, error } = useQuery({
    queryKey: ['sources'],
    queryFn: getSources,
    refetchInterval: 30_000,
  })

  if (isLoading) return <div className="loading">Loading scraper health...</div>
  if (error) return <div className="error-box">Failed to load sources: {error.message}</div>

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Scraper Health</div>
          <div className="page-subtitle">Monitor scraper status, run history, and errors.</div>
        </div>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Source</th>
              <th>Status</th>
              <th>Last Run</th>
              <th>Last Success</th>
              <th>Last Error</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {sources.map(src => <SourceRow key={src.name} source={src} />)}
            {!sources.length && (
              <tr><td colSpan={6} className="text-muted" style={{ textAlign: 'center', padding: 32 }}>No scrapers configured.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
