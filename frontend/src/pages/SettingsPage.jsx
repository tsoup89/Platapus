import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, Send, Clock, Play, RefreshCw, Bot } from 'lucide-react'
import {
  getSettings, updateSettings,
  getWebhooks, createWebhook, deleteWebhook, testWebhook,
  clearDuplicates, resetAlerts,
  getSchedulerStatus, runAllNow, reschedule,
  getFBSessionStatus, fbDebugScrape,
  updateSettings as saveSettings,
} from '../api'
import api from '../api'

function fmtDate(dt) {
  if (!dt) return 'Never'
  return new Date(dt + 'Z').toLocaleString()
}

function SchedulerSection() {
  const qc = useQueryClient()
  const [msg, setMsg] = useState(null)
  const [interval, setInterval_] = useState(60)

  const { data: status } = useQuery({
    queryKey: ['scheduler-status'],
    queryFn: getSchedulerStatus,
    refetchInterval: 30_000,
  })

  const { data: settings } = useQuery({ queryKey: ['settings'], queryFn: getSettings })
  const { data: webhooks } = useQuery({ queryKey: ['webhooks'], queryFn: getWebhooks })

  const runMut = useMutation({
    mutationFn: runAllNow,
    onSuccess: () => setMsg('✅ Full scrape queued — check Scraper Health for progress.'),
    onError: (e) => setMsg(`❌ ${e.message}`),
  })

  const rescheduleMut = useMutation({
    mutationFn: (m) => reschedule(m),
    onSuccess: (d) => { setMsg(`✅ Rescheduled to every ${d.interval_minutes} minutes.`); qc.invalidateQueries(['settings']) },
    onError: (e) => setMsg(`❌ ${e.message}`),
  })

  const enableMut = useMutation({
    mutationFn: (val) => api.post('/settings', { global_schedule_enabled: val }).then(r => r.data),
    onSuccess: () => qc.invalidateQueries(['settings', 'scheduler-status']),
  })

  const isEnabled = settings?.global_schedule_enabled ?? false
  const currentInterval = settings?.global_schedule_interval_minutes ?? 60

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Clock size={14} /> Automatic Scheduling
      </div>

      {msg && <div className={msg.startsWith('✅') ? 'success-box' : 'error-box'}>{msg}</div>}

      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 16 }}>
        <div>
          <span className={`badge ${isEnabled ? 'badge-green' : 'badge-gray'}`}>
            {isEnabled ? 'Enabled' : 'Disabled'}
          </span>
          {status?.running && (
            <span className="badge badge-blue" style={{ marginLeft: 8 }}>Scheduler running</span>
          )}
        </div>
        <button
          className={`btn btn-sm ${isEnabled ? 'btn-secondary' : 'btn-primary'}`}
          onClick={() => enableMut.mutate(!isEnabled)}
        >
          {isEnabled ? 'Disable Auto-Scrape' : 'Enable Auto-Scrape'}
        </button>
        <button
          className="btn btn-sm btn-primary"
          onClick={() => runMut.mutate()}
          disabled={runMut.isPending}
        >
          <Play size={12} /> Run All Now
        </button>
      </div>

      {status?.jobs?.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          {status.jobs.map(j => (
            <div key={j.id} style={{ fontSize: 13, color: 'var(--text-muted)' }}>
              Next run: <strong style={{ color: 'var(--text)' }}>{fmtDate(j.next_run)}</strong>
            </div>
          ))}
        </div>
      )}

      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8 }}>
        <div className="form-group" style={{ marginBottom: 0 }}>
          <label>Run interval (minutes)</label>
          <input
            type="number"
            style={{ width: 120 }}
            value={interval}
            onChange={e => setInterval_(+e.target.value)}
            min={5}
          />
        </div>
        <button
          className="btn btn-secondary btn-sm"
          onClick={() => rescheduleMut.mutate(interval)}
          disabled={rescheduleMut.isPending}
        >
          <RefreshCw size={12} /> Apply
        </button>
        <span className="text-muted" style={{ fontSize: 12, paddingBottom: 4 }}>
          Currently: every {currentInterval} min
        </span>
      </div>

      <hr className="section-divider" />
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>Heartbeat Alerts</div>
      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>
        After each scheduled run, send a Discord summary showing source health and counts.
      </div>
      <div className="grid-2">
        <div className="form-group">
          <label>Heartbeat Webhook</label>
          <select
            value={settings?.heartbeat_discord_webhook_id ?? ''}
            onChange={e => {
              const val = e.target.value ? +e.target.value : null
              api.post('/settings', { heartbeat_discord_webhook_id: val, heartbeat_enabled: !!val })
                .then(() => qc.invalidateQueries(['settings']))
            }}
          >
            <option value="">Disabled</option>
            {webhooks?.map(wh => <option key={wh.id} value={wh.id}>{wh.name}</option>)}
          </select>
        </div>
        <div style={{ display: 'flex', alignItems: 'flex-end', paddingBottom: 2 }}>
          <span className="text-muted" style={{ fontSize: 12 }}>
            {settings?.heartbeat_enabled
              ? '✅ Heartbeat enabled — summary sent after each run'
              : '—  Select a webhook to enable heartbeat'}
          </span>
        </div>
      </div>
    </div>
  )
}

function FacebookSection() {
  const [msg, setMsg] = useState(null)

  const { data: fbStatus } = useQuery({
    queryKey: ['fb-session'],
    queryFn: getFBSessionStatus,
    refetchInterval: 60_000,
  })

  const debugMut = useMutation({
    mutationFn: (kw) => fbDebugScrape(kw),
    onSuccess: (d) => setMsg(`✅ ${d.message}`),
    onError: (e) => setMsg(`❌ ${e.message}`),
  })

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <div className="card-title">Facebook Marketplace</div>
      {msg && <div className={msg.startsWith('✅') ? 'success-box' : 'error-box'}>{msg}</div>}

      <div style={{ marginBottom: 12 }}>
        {fbStatus?.has_session ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span className="badge badge-green">Session Active</span>
            <span className="text-muted" style={{ fontSize: 12 }}>
              Last saved: {fmtDate(fbStatus.last_modified)} ({fbStatus.session_size_bytes} bytes)
            </span>
          </div>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span className="badge badge-red">No Session</span>
            <span className="text-muted" style={{ fontSize: 12 }}>
              {fbStatus?.message}
            </span>
          </div>
        )}
      </div>

      <div className="actions-row">
        <div
          className="btn btn-secondary"
          style={{ cursor: 'default', fontSize: 12, color: 'var(--text-muted)' }}
        >
          🔑 To log in: run <code style={{ background: 'var(--bg)', padding: '1px 6px', borderRadius: 4 }}>python platapicker.py facebook-login</code> in your terminal
        </div>
      </div>

      <hr className="section-divider" />
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>Debug Scrape</div>
      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>
        Run a single Facebook search without saving results — check server logs for card count.
      </div>
      <div className="actions-row">
        {['GameCube', 'espresso machine', 'patio set'].map(kw => (
          <button
            key={kw}
            className="btn btn-sm btn-secondary"
            onClick={() => debugMut.mutate(kw)}
            disabled={debugMut.isPending}
          >
            Debug: "{kw}"
          </button>
        ))}
      </div>
    </div>
  )
}

function WebhooksSection() {
  const qc = useQueryClient()
  const [form, setForm] = useState({ name: '', webhook_url: '' })
  const [msg, setMsg] = useState(null)

  const { data: webhooks } = useQuery({ queryKey: ['webhooks'], queryFn: getWebhooks })

  const createMut = useMutation({
    mutationFn: createWebhook,
    onSuccess: () => { qc.invalidateQueries(['webhooks']); setForm({ name: '', webhook_url: '' }) },
  })
  const deleteMut = useMutation({
    mutationFn: deleteWebhook,
    onSuccess: () => qc.invalidateQueries(['webhooks']),
  })
  const testMut = useMutation({
    mutationFn: testWebhook,
    onSuccess: () => setMsg('✅ Test message sent!'),
    onError: (e) => setMsg(`❌ ${e?.response?.data?.detail || e.message}`),
  })

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <div className="card-title">Discord Webhooks</div>
      {msg && <div className={msg.startsWith('✅') ? 'success-box' : 'error-box'}>{msg}</div>}
      <div className="grid-2" style={{ marginBottom: 12 }}>
        <div className="form-group">
          <label>Name</label>
          <input type="text" placeholder="My Webhook" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
        </div>
        <div className="form-group">
          <label>Webhook URL</label>
          <input type="url" placeholder="https://discord.com/api/webhooks/..." value={form.webhook_url} onChange={e => setForm(f => ({ ...f, webhook_url: e.target.value }))} />
        </div>
      </div>
      <button
        className="btn btn-primary btn-sm"
        disabled={!form.name || !form.webhook_url}
        onClick={() => createMut.mutate(form)}
      >
        <Plus size={13} /> Add Webhook
      </button>

      {webhooks?.length > 0 && (
        <table style={{ marginTop: 16 }}>
          <thead>
            <tr>
              <th>Name</th>
              <th>URL</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {webhooks.map(wh => (
              <tr key={wh.id}>
                <td>{wh.name}</td>
                <td className="text-muted" style={{ fontSize: 12 }}>{wh.webhook_url.slice(0, 55)}...</td>
                <td>
                  <div className="actions-row">
                    <button className="btn btn-sm btn-secondary" onClick={() => testMut.mutate(wh.id)}>
                      <Send size={12} /> Test
                    </button>
                    <button
                      className="btn btn-sm btn-danger"
                      onClick={() => window.confirm('Delete this webhook?') && deleteMut.mutate(wh.id)}
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

function GlobalSettings() {
  const qc = useQueryClient()
  const [msg, setMsg] = useState(null)
  const { data: settings, isLoading } = useQuery({ queryKey: ['settings'], queryFn: getSettings })
  const [form, setForm] = useState(null)

  const saveMut = useMutation({
    mutationFn: updateSettings,
    onSuccess: () => { qc.invalidateQueries(['settings']); setMsg('✅ Settings saved.') },
    onError: (e) => setMsg(`❌ ${e.message}`),
  })

  if (isLoading) return <div className="loading">Loading settings...</div>
  const current = form || settings || {}
  const set = (k, v) => setForm(f => ({ ...(f || settings), [k]: v }))

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <div className="card-title">Deal Thresholds & Scoring</div>
      {msg && <div className={msg.startsWith('✅') ? 'success-box' : 'error-box'}>{msg}</div>}

      <div className="mb-16">
        <strong style={{ fontSize: 13 }}>Deal Rating Thresholds</strong>
        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>
          Price as a ratio of conservative value. E.g. 0.45 means price ≤ 45% of value = STEAL.
        </div>
        <div className="grid-2">
          {['STEAL', 'GREAT', 'GOOD', 'FAIR'].map(r => (
            <div className="form-group" key={r}>
              <label><span className={`rating-${r}`}>{r}</span> — max ratio</label>
              <input
                type="number"
                step="0.01"
                min="0.1"
                max="1.0"
                value={current.deal_thresholds?.[r] ?? 0.5}
                onChange={e => set('deal_thresholds', { ...(current.deal_thresholds || {}), [r]: +e.target.value })}
              />
            </div>
          ))}
        </div>
      </div>

      <hr className="section-divider" />

      <div className="mb-16">
        <strong style={{ fontSize: 13 }}>GameCube Scoring</strong>
        <div className="grid-3" style={{ marginTop: 8 }}>
          <div className="form-group">
            <label>Bundle Discount</label>
            <input type="number" step="0.01" value={current.gamecube_bundle_discount ?? 0.85} onChange={e => set('gamecube_bundle_discount', +e.target.value)} />
          </div>
          <div className="form-group">
            <label>Low Demand Discount</label>
            <input type="number" step="0.01" value={current.gamecube_low_demand_discount ?? 0.60} onChange={e => set('gamecube_low_demand_discount', +e.target.value)} />
          </div>
          <div className="form-group">
            <label>Platform Fee %</label>
            <input type="number" step="0.01" value={current.gamecube_platform_fee_pct ?? 0.13} onChange={e => set('gamecube_platform_fee_pct', +e.target.value)} />
          </div>
        </div>
      </div>

      <hr className="section-divider" />

      <div className="mb-16">
        <strong style={{ fontSize: 13 }}>Facebook Slow Mode</strong>
        <div className="grid-2" style={{ marginTop: 8 }}>
          <div className="form-group">
            <label>Min Delay (seconds)</label>
            <input type="number" value={current.facebook_min_delay_seconds ?? 3} onChange={e => set('facebook_min_delay_seconds', +e.target.value)} />
          </div>
          <div className="form-group">
            <label>Max Delay (seconds)</label>
            <input type="number" value={current.facebook_max_delay_seconds ?? 8} onChange={e => set('facebook_max_delay_seconds', +e.target.value)} />
          </div>
          <div className="form-group">
            <label>Max Listings Per Run</label>
            <input type="number" value={current.facebook_max_listings_per_run ?? 50} onChange={e => set('facebook_max_listings_per_run', +e.target.value)} />
          </div>
          <div className="form-group">
            <label>Max Searches Per Run</label>
            <input type="number" value={current.facebook_max_searches_per_run ?? 5} onChange={e => set('facebook_max_searches_per_run', +e.target.value)} />
          </div>
        </div>
      </div>

      <hr className="section-divider" />

      <div className="mb-16">
        <strong style={{ fontSize: 13 }}>Alert Batching</strong>
        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>
          Send batch summary instead of individual alerts when N+ deals qualify per run. 0 = always individual.
        </div>
        <div style={{ maxWidth: 200 }}>
          <div className="form-group">
            <label>Alert Batch Threshold</label>
            <input
              type="number"
              min="0"
              step="1"
              value={current.alert_batch_threshold ?? 3}
              onChange={e => set('alert_batch_threshold', +e.target.value)}
            />
          </div>
        </div>
      </div>

      <button className="btn btn-primary" onClick={() => saveMut.mutate(form || {})}>
        Save Settings
      </button>
    </div>
  )
}

function ClaudeSection() {
  const qc = useQueryClient()
  const [msg, setMsg] = useState(null)
  const [showKey, setShowKey] = useState(false)

  const { data: settings, isLoading } = useQuery({ queryKey: ['settings'], queryFn: getSettings })
  const [form, setForm] = useState(null)

  const saveMut = useMutation({
    mutationFn: updateSettings,
    onSuccess: () => { qc.invalidateQueries(['settings']); setMsg('✅ Claude settings saved.') },
    onError: (e) => setMsg(`❌ ${e.message}`),
  })

  if (isLoading) return null
  const current = form || settings || {}
  const set = (k, v) => setForm(f => ({ ...(f || settings), [k]: v }))

  const MODELS = [
    { id: 'claude-haiku-4-5', label: 'Haiku 4.5 — Fastest, cheapest' },
    { id: 'claude-sonnet-4-6', label: 'Sonnet 4.6 — Balanced' },
    { id: 'claude-opus-4-7', label: 'Opus 4.7 — Most capable' },
  ]

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Bot size={14} /> Claude Review Gate
      </div>
      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 16 }}>
        Before sending a Discord alert, Claude will analyze the listing photo and text to verify it's
        a genuine deal. Rejected listings are saved to the database but not alerted. Fails open —
        if the API is unreachable the alert still fires.
      </div>

      {msg && <div className={msg.startsWith('✅') ? 'success-box' : 'error-box'}>{msg}</div>}

      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 16 }}>
        <span className={`badge ${current.claude_enabled ? 'badge-green' : 'badge-gray'}`}>
          {current.claude_enabled ? 'Enabled' : 'Disabled'}
        </span>
        <button
          className={`btn btn-sm ${current.claude_enabled ? 'btn-secondary' : 'btn-primary'}`}
          onClick={() => {
            const next = !current.claude_enabled
            set('claude_enabled', next)
            api.post('/settings', { claude_enabled: next }).then(() => qc.invalidateQueries(['settings']))
          }}
        >
          {current.claude_enabled ? 'Disable' : 'Enable'} Claude Review
        </button>
      </div>

      <div className="grid-2">
        <div className="form-group">
          <label>Anthropic API Key</label>
          <div style={{ display: 'flex', gap: 6 }}>
            <input
              type={showKey ? 'text' : 'password'}
              placeholder="sk-ant-..."
              value={current.claude_api_key || ''}
              onChange={e => set('claude_api_key', e.target.value)}
              style={{ flex: 1 }}
            />
            <button
              className="btn btn-sm btn-secondary"
              onClick={() => setShowKey(v => !v)}
              style={{ whiteSpace: 'nowrap' }}
            >
              {showKey ? 'Hide' : 'Show'}
            </button>
          </div>
          <div className="field-hint">
            Get your key at <a href="https://console.anthropic.com" target="_blank" rel="noreferrer" style={{ color: 'var(--accent)' }}>console.anthropic.com</a>
          </div>
        </div>

        <div className="form-group">
          <label>Model</label>
          <select
            value={current.claude_model || 'claude-haiku-4-5'}
            onChange={e => set('claude_model', e.target.value)}
          >
            {MODELS.map(m => (
              <option key={m.id} value={m.id}>{m.label}</option>
            ))}
          </select>
          <div className="field-hint">Haiku is recommended — fast and cheap for screening.</div>
        </div>
      </div>

      <button
        className="btn btn-primary btn-sm"
        onClick={() => saveMut.mutate({ claude_enabled: current.claude_enabled, claude_api_key: current.claude_api_key, claude_model: current.claude_model })}
        disabled={saveMut.isPending}
      >
        Save Claude Settings
      </button>
    </div>
  )
}

function MaintenanceSection() {
  const [msg, setMsg] = useState(null)

  const clearMut = useMutation({
    mutationFn: clearDuplicates,
    onSuccess: (d) => setMsg(`✅ ${d.message}`),
    onError: (e) => setMsg(`❌ ${e.message}`),
  })
  const resetMut = useMutation({
    mutationFn: resetAlerts,
    onSuccess: (d) => setMsg(`✅ ${d.message}`),
    onError: (e) => setMsg(`❌ ${e.message}`),
  })

  return (
    <div className="card">
      <div className="card-title">Maintenance</div>
      {msg && <div className={msg.startsWith('✅') ? 'success-box' : 'error-box'}>{msg}</div>}
      <div className="actions-row">
        <button
          className="btn btn-secondary"
          onClick={() => window.confirm('Clear all listing history? This cannot be undone.') && clearMut.mutate()}
        >
          Clear Duplicate Cache
        </button>
        <button
          className="btn btn-secondary"
          onClick={() => window.confirm('Reset all alert flags? All listings can be re-alerted.') && resetMut.mutate()}
        >
          Reset Alert Flags
        </button>
      </div>
      <div className="text-muted" style={{ fontSize: 12, marginTop: 12 }}>
        <strong>Clear Duplicate Cache:</strong> Removes all saved listings. Next scrape re-imports everything from scratch.<br />
        <strong>Reset Alert Flags:</strong> Allows existing listings to be re-alerted on next scrape.
      </div>
    </div>
  )
}

export default function SettingsPage() {
  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Settings</div>
          <div className="page-subtitle">Configure scheduling, Discord, Facebook, and deal thresholds.</div>
        </div>
      </div>
      <SchedulerSection />
      <WebhooksSection />
      <FacebookSection />
      <GlobalSettings />
      <ClaudeSection />
      <MaintenanceSection />
    </div>
  )
}
