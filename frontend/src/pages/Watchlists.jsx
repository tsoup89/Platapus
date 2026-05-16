import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Edit, Trash2, ToggleLeft, ToggleRight } from 'lucide-react'
import { getWatchlists, createWatchlist, updateWatchlist, deleteWatchlist, toggleWatchlist, getWebhooks } from '../api'

const EMPTY_FORM = {
  name: '', enabled: true, category: '', keywords: [], negative_keywords: [],
  brands: [], aliases: [], locations: [], radius_miles: 50, min_price: 0,
  max_price: 99999, sources_enabled: [], run_frequency_minutes: 60,
  min_rating_to_alert: 'GOOD', min_profit_margin: 0.20, min_profit_dollars: 50,
  discord_webhook_id: null, notes: '',
}

function tagsToList(str) {
  return str.split(',').map(s => s.trim()).filter(Boolean)
}

function listToTags(arr) {
  return Array.isArray(arr) ? arr.join(', ') : ''
}

function WatchlistModal({ initial, webhooks, onClose, onSave }) {
  const [form, setForm] = useState(initial || EMPTY_FORM)
  const [error, setError] = useState(null)

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    try {
      await onSave({
        ...form,
        keywords: typeof form.keywords === 'string' ? tagsToList(form.keywords) : form.keywords,
        negative_keywords: typeof form.negative_keywords === 'string' ? tagsToList(form.negative_keywords) : form.negative_keywords,
        brands: typeof form.brands === 'string' ? tagsToList(form.brands) : form.brands,
        locations: typeof form.locations === 'string' ? tagsToList(form.locations) : form.locations,
        sources_enabled: typeof form.sources_enabled === 'string' ? tagsToList(form.sources_enabled) : form.sources_enabled,
      })
      onClose()
    } catch (err) {
      setError(err?.response?.data?.detail || String(err))
    }
  }

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        <div className="modal-header">
          <div className="modal-title">{initial ? 'Edit Watchlist' : 'New Watchlist'}</div>
          <button className="btn btn-secondary btn-sm" onClick={onClose}>✕</button>
        </div>
        {error && <div className="error-box">{error}</div>}
        <form onSubmit={handleSubmit}>
          <div className="grid-2">
            <div className="form-group">
              <label>Name</label>
              <input type="text" value={form.name} onChange={e => set('name', e.target.value)} required />
            </div>
            <div className="form-group">
              <label>Category</label>
              <select value={form.category || ''} onChange={e => set('category', e.target.value)}>
                <option value="">General</option>
                <option value="gamecube">GameCube</option>
                <option value="espresso">Espresso</option>
                <option value="outdoor_furniture">Outdoor Furniture</option>
              </select>
            </div>
          </div>

          <div className="form-group">
            <label>Keywords (comma-separated)</label>
            <textarea
              value={listToTags(form.keywords)}
              onChange={e => set('keywords', e.target.value)}
              placeholder="espresso machine, coffee grinder, dual boiler"
            />
          </div>

          <div className="form-group">
            <label>Negative Keywords (comma-separated)</label>
            <textarea
              value={listToTags(form.negative_keywords)}
              onChange={e => set('negative_keywords', e.target.value)}
              placeholder="broken, parts only, nespresso"
            />
          </div>

          <div className="form-group">
            <label>Brands (comma-separated)</label>
            <textarea
              value={listToTags(form.brands)}
              onChange={e => set('brands', e.target.value)}
              placeholder="La Marzocco, Profitec, Rancilio"
            />
          </div>

          <div className="form-group">
            <label>Locations (comma-separated)</label>
            <input
              type="text"
              value={listToTags(form.locations)}
              onChange={e => set('locations', e.target.value)}
              placeholder="New York, NY"
            />
          </div>

          <div className="grid-3">
            <div className="form-group">
              <label>Radius (miles)</label>
              <input type="number" value={form.radius_miles} onChange={e => set('radius_miles', +e.target.value)} />
            </div>
            <div className="form-group">
              <label>Min Price ($)</label>
              <input type="number" value={form.min_price} onChange={e => set('min_price', +e.target.value)} />
            </div>
            <div className="form-group">
              <label>Max Price ($)</label>
              <input type="number" value={form.max_price} onChange={e => set('max_price', +e.target.value)} />
            </div>
          </div>

          <div className="grid-2">
            <div className="form-group">
              <label>Sources Enabled</label>
              <input
                type="text"
                value={listToTags(form.sources_enabled)}
                onChange={e => set('sources_enabled', e.target.value)}
                placeholder="facebook, auctionninja"
              />
            </div>
            <div className="form-group">
              <label>Min Alert Rating</label>
              <select value={form.min_rating_to_alert} onChange={e => set('min_rating_to_alert', e.target.value)}>
                <option value="STEAL">STEAL only</option>
                <option value="GREAT">GREAT+</option>
                <option value="GOOD">GOOD+</option>
                <option value="FAIR">FAIR+</option>
              </select>
            </div>
          </div>

          <div className="grid-2">
            <div className="form-group">
              <label>Min Profit Margin</label>
              <input type="number" step="0.01" value={form.min_profit_margin} onChange={e => set('min_profit_margin', +e.target.value)} />
            </div>
            <div className="form-group">
              <label>Min Profit ($)</label>
              <input type="number" value={form.min_profit_dollars} onChange={e => set('min_profit_dollars', +e.target.value)} />
            </div>
          </div>

          <div className="form-group">
            <label>Discord Webhook</label>
            <select
              value={form.discord_webhook_id || ''}
              onChange={e => set('discord_webhook_id', e.target.value ? +e.target.value : null)}
            >
              <option value="">None</option>
              {webhooks?.map(wh => <option key={wh.id} value={wh.id}>{wh.name}</option>)}
            </select>
          </div>

          <div className="form-group">
            <label>Notes</label>
            <textarea value={form.notes} onChange={e => set('notes', e.target.value)} />
          </div>

          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 8 }}>
            <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary">Save</button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default function Watchlists() {
  const qc = useQueryClient()
  const [modal, setModal] = useState(null)

  const { data: watchlists, isLoading } = useQuery({ queryKey: ['watchlists'], queryFn: getWatchlists })
  const { data: webhooks } = useQuery({ queryKey: ['webhooks'], queryFn: getWebhooks })

  const createMut = useMutation({ mutationFn: createWatchlist, onSuccess: () => qc.invalidateQueries(['watchlists']) })
  const updateMut = useMutation({ mutationFn: ({ id, data }) => updateWatchlist(id, data), onSuccess: () => qc.invalidateQueries(['watchlists']) })
  const deleteMut = useMutation({ mutationFn: deleteWatchlist, onSuccess: () => qc.invalidateQueries(['watchlists']) })
  const toggleMut = useMutation({ mutationFn: toggleWatchlist, onSuccess: () => qc.invalidateQueries(['watchlists']) })

  if (isLoading) return <div className="loading">Loading watchlists...</div>

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Watchlists</div>
          <div className="page-subtitle">Configure what to search for and where to alert.</div>
        </div>
        <button className="btn btn-primary" onClick={() => setModal({ type: 'create' })}>
          <Plus size={14} /> New Watchlist
        </button>
      </div>

      {modal?.type === 'create' && (
        <WatchlistModal
          webhooks={webhooks}
          onClose={() => setModal(null)}
          onSave={data => createMut.mutateAsync(data)}
        />
      )}
      {modal?.type === 'edit' && (
        <WatchlistModal
          initial={modal.watchlist}
          webhooks={webhooks}
          onClose={() => setModal(null)}
          onSave={data => updateMut.mutateAsync({ id: modal.watchlist.id, data })}
        />
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {watchlists?.map(wl => (
          <div key={wl.id} className="card" style={{ opacity: wl.enabled ? 1 : 0.6 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
                  <strong style={{ fontSize: 15 }}>{wl.name}</strong>
                  {wl.category && <span className="badge badge-blue">{wl.category}</span>}
                  {wl.enabled
                    ? <span className="badge badge-green">Active</span>
                    : <span className="badge badge-gray">Disabled</span>}
                </div>
                <div className="text-muted" style={{ fontSize: 12, marginBottom: 8 }}>
                  Min alert: <strong>{wl.min_rating_to_alert}</strong> &nbsp;·&nbsp;
                  Radius: <strong>{wl.radius_miles}mi</strong> &nbsp;·&nbsp;
                  Price: <strong>${wl.min_price}–${wl.max_price}</strong> &nbsp;·&nbsp;
                  Run every: <strong>{wl.run_frequency_minutes}min</strong>
                </div>
                {wl.keywords?.length > 0 && (
                  <div className="tag-list">
                    {wl.keywords.slice(0, 5).map(k => <span key={k} className="tag">{k}</span>)}
                    {wl.keywords.length > 5 && <span className="text-muted" style={{ fontSize: 11 }}>+{wl.keywords.length - 5} more</span>}
                  </div>
                )}
              </div>
              <div className="actions-row">
                <button className="btn btn-sm btn-secondary" onClick={() => toggleMut.mutate(wl.id)} title="Toggle enabled">
                  {wl.enabled ? <ToggleRight size={14} color="var(--green)" /> : <ToggleLeft size={14} />}
                </button>
                <button className="btn btn-sm btn-secondary" onClick={() => setModal({ type: 'edit', watchlist: wl })}>
                  <Edit size={13} />
                </button>
                <button
                  className="btn btn-sm btn-danger"
                  onClick={() => window.confirm(`Delete watchlist "${wl.name}"?`) && deleteMut.mutate(wl.id)}
                >
                  <Trash2 size={13} />
                </button>
              </div>
            </div>
          </div>
        ))}
        {!watchlists?.length && (
          <div className="empty-state">
            <div className="icon">📋</div>
            <div>No watchlists yet. Create one to start monitoring deals.</div>
          </div>
        )}
      </div>
    </div>
  )
}
