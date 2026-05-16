import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, Send } from 'lucide-react'
import {
  getSettings, updateSettings,
  getWebhooks, createWebhook, deleteWebhook, testWebhook,
  clearDuplicates, resetAlerts,
} from '../api'

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
                <td className="text-muted" style={{ fontSize: 12 }}>{wh.webhook_url.slice(0, 60)}...</td>
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
      <div className="card-title">Global Settings</div>
      {msg && <div className={msg.startsWith('✅') ? 'success-box' : 'error-box'}>{msg}</div>}

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
        <strong style={{ fontSize: 13 }}>Deal Thresholds</strong>
        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>
          Price as % of conservative value to earn each rating.
        </div>
        <div className="grid-2">
          {['STEAL', 'GREAT', 'GOOD', 'FAIR'].map(r => (
            <div className="form-group" key={r}>
              <label>{r} (ratio, e.g. 0.45 = 45%)</label>
              <input
                type="number"
                step="0.01"
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
            <label>Platform Fee</label>
            <input type="number" step="0.01" value={current.gamecube_platform_fee_pct ?? 0.13} onChange={e => set('gamecube_platform_fee_pct', +e.target.value)} />
          </div>
        </div>
      </div>

      <button className="btn btn-primary" onClick={() => saveMut.mutate(form || {})}>
        Save Settings
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
          onClick={() => window.confirm('Clear all listing history?') && clearMut.mutate()}
        >
          Clear Duplicate Cache
        </button>
        <button
          className="btn btn-secondary"
          onClick={() => window.confirm('Reset all alert flags?') && resetMut.mutate()}
        >
          Reset Alert Flags
        </button>
      </div>
      <div className="text-muted" style={{ fontSize: 12, marginTop: 12 }}>
        Clearing the duplicate cache will remove all saved listings. New scrapes will re-import them.
        Resetting alert flags allows all existing listings to be re-alerted.
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
          <div className="page-subtitle">Configure Discord webhooks, scraper behavior, and deal thresholds.</div>
        </div>
      </div>
      <WebhooksSection />
      <GlobalSettings />
      <MaintenanceSection />
    </div>
  )
}
