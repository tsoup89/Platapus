import { useState, useRef, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Package, Plus, X, Upload, Trash2,
  Zap, ExternalLink, RefreshCw, TrendingUp, DollarSign,
  ShoppingBag, CheckCircle, AlertCircle, Clock, Link, Sparkles,
} from 'lucide-react'
import {
  getInventory, createInventoryItem, getInventoryItem,
  updateInventoryItem, deleteInventoryItem, uploadInventoryPhotos,
  deleteInventoryPhoto, inventoryPhotoUrl,
  triggerPriceSuggestion,
  getSellListings, createSellListing, updateSellListing,
  markSellListingSold, removeSellListing,
} from '../api'

const CLAUDE_INVENTORY_PROMPT = `You are analyzing an item someone wants to sell on Facebook Marketplace or eBay.
Return ONLY a JSON object — no markdown fences, no prose. Use this exact schema:
{
  "title": "concise listing title including brand/model if visible (e.g. 'Nintendo GameCube Console Purple')",
  "category": "single-word or short category (e.g. gaming, electronics, furniture, clothing, tools, appliances)",
  "condition": "exactly one of: NEW, LIKE_NEW, GOOD, FAIR, POOR",
  "description": "2-3 sentence listing description mentioning key features and any visible wear or issues"
}`

async function openInventoryInClaude() {
  const msg = `Upload a photo of your item along with this prompt:\n\n${CLAUDE_INVENTORY_PROMPT}`
  try {
    if (window.platapicker?.copyToClipboard) {
      await window.platapicker.copyToClipboard(msg)
    } else {
      await navigator.clipboard.writeText(msg)
    }
  } catch (_) {}
  const url = 'https://claude.ai/new'
  if (window.platapicker?.openExternal) {
    window.platapicker.openExternal(url)
  } else {
    window.open(url, '_blank')
  }
}

const CONDITIONS = [
  { value: 'NEW', label: 'New' },
  { value: 'LIKE_NEW', label: 'Like New' },
  { value: 'GOOD', label: 'Good' },
  { value: 'FAIR', label: 'Fair' },
  { value: 'POOR', label: 'Poor' },
]

const STATUSES = [
  { value: 'DRAFT', label: 'Draft', color: 'gray' },
  { value: 'LISTED', label: 'Listed', color: 'blue' },
  { value: 'SOLD', label: 'Sold', color: 'green' },
  { value: 'ARCHIVED', label: 'Archived', color: 'gray' },
]

const PLATFORM_META = {
  ebay:     { label: 'eBay',      color: '#e43137', fee: 0.1325 },
  facebook: { label: 'Facebook',  color: '#1877f2', fee: 0.05   },
}

function statusBadge(status) {
  const s = STATUSES.find(s => s.value === status) || STATUSES[0]
  return <span className={`badge badge-${s.color}`}>{s.label}</span>
}

function fmtMoney(v) {
  if (v == null) return '—'
  return `$${Number(v).toFixed(2)}`
}

export default function Inventory() {
  const qc = useQueryClient()
  const [openId, setOpenId] = useState(null)
  const [creating, setCreating] = useState(false)

  const { data: items = [], isLoading } = useQuery({
    queryKey: ['inventory'],
    queryFn: () => getInventory(),
  })

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Inventory</div>
          <div className="page-subtitle">Items you own and are preparing to sell.</div>
        </div>
        <button className="btn btn-success" onClick={() => setCreating(true)}>
          <Plus size={14} /> Add item
        </button>
      </div>

      {isLoading && <div className="loading">Loading inventory…</div>}

      {!isLoading && items.length === 0 && (
        <div className="empty-state">
          <Package size={36} style={{ opacity: 0.4, marginBottom: 12 }} />
          <div>No inventory yet.</div>
          <div style={{ fontSize: 12, marginTop: 6 }}>
            Add an item manually, or use "Mark as purchased" on a buy-side listing.
          </div>
        </div>
      )}

      {!isLoading && items.length > 0 && (
        <div className="inventory-grid">
          {items.map(item => (
            <InventoryCard key={item.id} item={item} onClick={() => setOpenId(item.id)} />
          ))}
        </div>
      )}

      {creating && (
        <CreateItemDrawer
          onClose={() => setCreating(false)}
          onCreated={(id) => {
            setCreating(false)
            qc.invalidateQueries({ queryKey: ['inventory'] })
            setOpenId(id)
          }}
        />
      )}

      {openId != null && (
        <ItemDetailDrawer
          itemId={openId}
          onClose={() => {
            setOpenId(null)
            qc.invalidateQueries({ queryKey: ['inventory'] })
          }}
        />
      )}
    </div>
  )
}

function InventoryCard({ item, onClick }) {
  const firstPhoto = item.photos?.[0]
  const ps = item.price_suggestion
  return (
    <div className="inv-card" onClick={onClick}>
      <div className="inv-card-thumb">
        {firstPhoto ? (
          <img src={inventoryPhotoUrl(firstPhoto)} alt="" />
        ) : (
          <Package size={28} className="inv-card-thumb-empty" />
        )}
        <div className="inv-card-status">{statusBadge(item.status)}</div>
      </div>
      <div className="inv-card-body">
        <div className="inv-card-title">{item.title}</div>
        <div className="inv-card-meta">
          <span>Paid {fmtMoney(item.purchase_price)}</span>
          {item.listed_price
            ? <span style={{ color: 'var(--green)', fontWeight: 600 }}>List {fmtMoney(item.listed_price)}</span>
            : ps?.suggested_price
              ? <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>~{fmtMoney(ps.suggested_price)}</span>
              : <span>{item.condition?.replace('_', ' ').toLowerCase() || 'good'}</span>
          }
        </div>
      </div>
    </div>
  )
}

function CreateItemDrawer({ onClose, onCreated }) {
  const [form, setForm] = useState({
    title: '', description: '', category: '',
    condition: 'GOOD', purchase_price: '', notes: '', status: 'DRAFT',
  })
  const [error, setError] = useState(null)
  const [jsonPaste, setJsonPaste] = useState('')
  const [jsonError, setJsonError] = useState(null)
  const [copied, setCopied] = useState(false)

  const mut = useMutation({
    mutationFn: () => createInventoryItem({
      ...form,
      purchase_price: form.purchase_price ? parseFloat(form.purchase_price) : null,
      category: form.category || null,
    }),
    onSuccess: (item) => onCreated(item.id),
    onError: (e) => setError(e?.response?.data?.detail || e.message),
  })

  async function handleOpenClaude() {
    await openInventoryInClaude()
    setCopied(true)
    setTimeout(() => setCopied(false), 3000)
  }

  function handleApplyJson() {
    setJsonError(null)
    try {
      let raw = jsonPaste.trim()
      if (raw.startsWith('```')) {
        raw = raw.split('\n').slice(1).join('\n').replace(/```$/, '').trim()
      }
      const data = JSON.parse(raw)
      setForm(f => ({
        ...f,
        title: data.title || f.title,
        category: data.category || f.category,
        condition: data.condition || f.condition,
        description: data.description || f.description,
      }))
      setJsonPaste('')
    } catch {
      setJsonError('Could not parse JSON — make sure you copied the full response from Claude.')
    }
  }

  return (
    <>
      <div className="drawer-overlay" onClick={onClose} />
      <aside className="drawer">
        <div className="drawer-header">
          <div className="modal-title">Add inventory item</div>
          <button className="btn btn-secondary btn-sm" onClick={onClose}><X size={14} /></button>
        </div>
        <div className="drawer-body">
          {error && <div className="error-box">{error}</div>}

          <div className="claude-assistant" style={{ marginBottom: 16 }}>
            <div className="claude-assistant-header">
              <Sparkles size={14} style={{ color: 'var(--accent)' }} />
              <span>Fill with Claude</span>
            </div>
            <button
              type="button"
              className="btn btn-accent btn-sm"
              onClick={handleOpenClaude}
              style={{ width: '100%', marginBottom: 8 }}
            >
              {copied
                ? <><RefreshCw size={13} /> Prompt copied! Paste it in Claude with your photo</>
                : <><ExternalLink size={13} /> Copy prompt &amp; open Claude →</>}
            </button>
            <textarea
              value={jsonPaste}
              onChange={e => { setJsonPaste(e.target.value); setJsonError(null) }}
              placeholder="Paste Claude's JSON response here…"
              style={{ width: '100%', minHeight: 70, fontFamily: 'monospace', fontSize: 11, boxSizing: 'border-box' }}
            />
            {jsonError && <div className="claude-error" style={{ marginBottom: 4 }}>{jsonError}</div>}
            {jsonPaste.trim() && (
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={handleApplyJson}
                style={{ width: '100%', marginTop: 4 }}
              >
                Apply to form
              </button>
            )}
          </div>

          <div className="form-section">
            <div className="form-group">
              <label>Title</label>
              <input type="text" value={form.title}
                onChange={e => setForm({ ...form, title: e.target.value })}
                placeholder="e.g. Super Smash Bros Melee (Complete)" autoFocus />
            </div>
            <div className="grid-2">
              <div className="form-group">
                <label>Condition</label>
                <select value={form.condition} onChange={e => setForm({ ...form, condition: e.target.value })}>
                  {CONDITIONS.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Purchase price</label>
                <input type="number" step="0.01" value={form.purchase_price}
                  onChange={e => setForm({ ...form, purchase_price: e.target.value })} placeholder="0.00" />
              </div>
            </div>
            <div className="form-group">
              <label>Category <span className="label-hint">optional</span></label>
              <input type="text" value={form.category}
                onChange={e => setForm({ ...form, category: e.target.value })}
                placeholder="e.g. gamecube, electronics, furniture" />
            </div>
            <div className="form-group">
              <label>Description <span className="label-hint">optional</span></label>
              <textarea value={form.description} onChange={e => setForm({ ...form, description: e.target.value })}
                placeholder="Anything you'd put in a listing later." />
            </div>
            <div className="form-group">
              <label>Internal notes <span className="label-hint">optional</span></label>
              <textarea value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })}
                placeholder="Where you bought it, any defects, etc." />
            </div>
          </div>
        </div>
        <div className="drawer-footer">
          <button className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn btn-success" disabled={!form.title.trim() || mut.isPending}
            onClick={() => { setError(null); mut.mutate() }}>
            {mut.isPending ? 'Creating…' : 'Create item'}
          </button>
        </div>
      </aside>
    </>
  )
}

// ─── Confidence badge ────────────────────────────────────────

function ConfidenceBadge({ confidence }) {
  const map = {
    high:    { label: 'High confidence',   color: 'var(--green)' },
    medium:  { label: 'Medium confidence', color: '#f59e0b' },
    low:     { label: 'Low confidence',    color: '#ef4444' },
    none:    { label: 'No data',           color: 'var(--text-muted)' },
    pending: { label: 'Analysing…',        color: 'var(--text-muted)' },
  }
  const c = map[confidence] || map.none
  return (
    <span style={{
      fontSize: 11, fontWeight: 600, color: c.color,
      background: c.color + '22', borderRadius: 4, padding: '2px 7px',
    }}>{c.label}</span>
  )
}

// ─── Auto-price panel ────────────────────────────────────────

function AutoPricePanel({ item, onUseSuggestedPrice }) {
  const qc = useQueryClient()
  const ps = item.price_suggestion
  const isPending = ps?.confidence === 'pending'

  const triggerMut = useMutation({
    mutationFn: () => triggerPriceSuggestion(item.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['inventory', item.id] }),
  })

  useEffect(() => {
    if (!isPending) return
    const iv = setInterval(() => {
      qc.invalidateQueries({ queryKey: ['inventory', item.id] })
    }, 3000)
    return () => clearInterval(iv)
  }, [isPending, item.id, qc])

  const hasResult = ps && ps.confidence !== 'pending' && ps.confidence !== 'none'

  return (
    <div className="auto-price-panel">
      <div className="auto-price-header">
        <div className="auto-price-title">
          <TrendingUp size={14} style={{ color: 'var(--green)' }} />
          Auto-price analysis
        </div>
        <button className="btn btn-secondary btn-sm"
          disabled={triggerMut.isPending || isPending}
          onClick={() => triggerMut.mutate()} title="Re-run price analysis">
          {(triggerMut.isPending || isPending)
            ? <><RefreshCw size={12} className="spin" /> Analysing…</>
            : <><Zap size={12} /> {ps ? 'Re-analyse' : 'Suggest price'}</>
          }
        </button>
      </div>

      {!ps && (
        <div className="auto-price-empty">
          Click "Suggest price" to fetch live comps from eBay and Mercari
          and get a recommended sell price based on your item's condition.
        </div>
      )}
      {isPending && (
        <div className="auto-price-loading">
          <RefreshCw size={14} className="spin" />
          Fetching comps from eBay and Mercari… this takes ~20–30 s
        </div>
      )}
      {ps && ps.error && ps.confidence !== 'pending' && (
        <div className="auto-price-error">{ps.error}</div>
      )}
      {hasResult && (
        <>
          <div className="auto-price-result">
            <div className="auto-price-price">
              <span className="auto-price-label">Suggested price</span>
              <span className="auto-price-amount">{fmtMoney(ps.suggested_price)}</span>
              <ConfidenceBadge confidence={ps.confidence} />
            </div>
            <div className="auto-price-range">
              <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>
                Range: {fmtMoney(ps.low_estimate)} – {fmtMoney(ps.high_estimate)}
              </span>
              <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>
                Condition: {ps.condition_applied?.replace('_', ' ')}
              </span>
            </div>
            <button className="btn btn-success btn-sm" style={{ alignSelf: 'flex-start' }}
              onClick={() => onUseSuggestedPrice(ps.suggested_price)}>
              <DollarSign size={12} /> Use this price
            </button>
          </div>
          {ps.comps?.length > 0 && (
            <div className="auto-price-comps">
              <div className="auto-price-comps-title">Comparable listings ({ps.comps.length})</div>
              <div className="auto-price-comps-table">
                {ps.comps.map((comp, i) => (
                  <div key={i} className="auto-price-comp-row">
                    <span className={`comp-badge comp-${comp.is_sold ? 'sold' : 'active'}`}>
                      {comp.is_sold ? 'SOLD' : 'ACTIVE'}
                    </span>
                    <span className="comp-source">{comp.source}</span>
                    <span className="comp-title" title={comp.title}>
                      {comp.url
                        ? <a href={comp.url} target="_blank" rel="noreferrer">
                            {comp.title} <ExternalLink size={10} style={{ opacity: 0.6 }} />
                          </a>
                        : comp.title}
                    </span>
                    <span className="comp-price">{fmtMoney(comp.price)}</span>
                  </div>
                ))}
              </div>
              {ps.generated_at && (
                <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 6 }}>
                  Last updated {new Date(ps.generated_at).toLocaleString()}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}

// ─── Sell listings panel ─────────────────────────────────────

function SellListingStatusBadge({ status }) {
  const map = {
    DRAFT:    { label: 'Draft',    bg: 'rgba(148,163,184,0.15)', color: '#94a3b8' },
    POSTING:  { label: 'Posting…', bg: 'rgba(251,191,36,0.15)',  color: '#fbbf24' },
    POSTED:   { label: 'Posted',   bg: 'rgba(59,130,246,0.15)',  color: '#3b82f6' },
    SOLD:     { label: 'Sold',     bg: 'rgba(34,197,94,0.15)',   color: 'var(--green)' },
    REMOVED:  { label: 'Removed',  bg: 'rgba(148,163,184,0.15)', color: '#94a3b8' },
    FAILED:   { label: 'Failed',   bg: 'rgba(239,68,68,0.15)',   color: '#ef4444' },
  }
  const s = map[status] || map.DRAFT
  return (
    <span style={{
      fontSize: 10, fontWeight: 700, borderRadius: 4, padding: '2px 7px',
      background: s.bg, color: s.color,
    }}>{s.label}</span>
  )
}

function PlatformBadge({ platform }) {
  const m = PLATFORM_META[platform] || { label: platform, color: '#888' }
  return (
    <span style={{
      fontSize: 10, fontWeight: 700, borderRadius: 4, padding: '2px 8px',
      background: m.color + '22', color: m.color, textTransform: 'uppercase',
    }}>{m.label}</span>
  )
}

function SellListingCard({ sl, itemId, item }) {
  const qc = useQueryClient()
  const [markingSold, setMarkingSold] = useState(false)
  const [soldForm, setSoldForm] = useState({
    sale_price: sl.listed_price || '',
    platform_fees: '',
    shipping_cost: '0',
    platform_listing_id: '',
    platform_url: sl.platform_url || '',
  })
  const [urlForm, setUrlForm] = useState({ platform_url: sl.platform_url || '' })
  const [editingUrl, setEditingUrl] = useState(false)

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['sell-listings', itemId] })
    qc.invalidateQueries({ queryKey: ['inventory', itemId] })
    qc.invalidateQueries({ queryKey: ['inventory'] })
  }

  const removeMut = useMutation({
    mutationFn: () => removeSellListing(sl.id),
    onSuccess: invalidate,
  })

  const soldMut = useMutation({
    mutationFn: () => markSellListingSold(sl.id, {
      sale_price: parseFloat(soldForm.sale_price),
      platform_fees: soldForm.platform_fees ? parseFloat(soldForm.platform_fees) : undefined,
      shipping_cost: parseFloat(soldForm.shipping_cost || 0),
      platform_listing_id: soldForm.platform_listing_id || undefined,
      platform_url: soldForm.platform_url || undefined,
    }),
    onSuccess: () => { setMarkingSold(false); invalidate() },
  })

  const updateUrlMut = useMutation({
    mutationFn: () => updateSellListing(sl.id, {
      platform_url: urlForm.platform_url || undefined,
      status: 'POSTED',
    }),
    onSuccess: () => { setEditingUrl(false); invalidate() },
  })

  const pm = PLATFORM_META[sl.platform] || { label: sl.platform, color: '#888', fee: 0 }
  const estFee = soldForm.sale_price
    ? (parseFloat(soldForm.sale_price) * pm.fee).toFixed(2)
    : '—'

  return (
    <div className="sell-listing-card">
      {/* Header row */}
      <div className="sell-listing-header">
        <PlatformBadge platform={sl.platform} />
        <SellListingStatusBadge status={sl.status} />
        <span style={{ fontSize: 12, fontWeight: 600 }}>{fmtMoney(sl.listed_price)}</span>
        <div style={{ flex: 1 }} />
        {sl.status === 'SOLD' && (
          <span style={{ fontSize: 11, color: 'var(--green)' }}>
            Sold {fmtMoney(sl.sale_price)} · Net {fmtMoney(
              (sl.sale_price || 0) - (sl.platform_fees || 0) - (sl.shipping_cost || 0)
            )}
          </span>
        )}
      </div>

      {/* POSTING spinner */}
      {sl.status === 'POSTING' && (
        <div className="sell-listing-posting">
          <RefreshCw size={13} className="spin" />
          Playwright is filling in your Facebook listing… check back in ~30 s
        </div>
      )}

      {/* FAILED */}
      {sl.status === 'FAILED' && (
        <div className="sell-listing-error">
          <AlertCircle size={13} />
          <span>{sl.error_message || 'Listing automation failed.'}</span>
        </div>
      )}

      {/* DRAFT (eBay) — show pre-fill card + "open" button */}
      {sl.status === 'DRAFT' && sl.platform === 'ebay' && (
        <div className="sell-listing-draft-ebay">
          <div className="sell-listing-draft-copy">
            <div><strong>Title:</strong> {item?.title || sl.raw_metadata?.title || '—'}</div>
            {item?.description && <div><strong>Description:</strong> <span style={{color:'var(--text-muted)'}}>{item.description.slice(0,120)}{item.description.length > 120 ? '…' : ''}</span></div>}
            <div><strong>Price:</strong> {fmtMoney(sl.listed_price)}</div>
            <div><strong>Condition:</strong> {item?.condition?.replace('_',' ') || '—'}</div>
            <div><strong>Est. fee:</strong> {fmtMoney(sl.listed_price * pm.fee)} (13.25% FVF)</div>
          </div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 8 }}>
            <a href={sl.action_url} target="_blank" rel="noreferrer"
              className="btn btn-secondary btn-sm">
              <ExternalLink size={12} /> Open eBay listing form
            </a>
            <button className="btn btn-secondary btn-sm"
              onClick={() => setEditingUrl(v => !v)}>
              <Link size={12} /> I've posted it — enter URL
            </button>
          </div>
          {editingUrl && (
            <div style={{ marginTop: 8, display: 'flex', gap: 6 }}>
              <input type="text" value={urlForm.platform_url} placeholder="https://www.ebay.com/itm/..."
                onChange={e => setUrlForm({ platform_url: e.target.value })}
                style={{ flex: 1, fontSize: 12 }} />
              <button className="btn btn-success btn-sm"
                disabled={!urlForm.platform_url || updateUrlMut.isPending}
                onClick={() => updateUrlMut.mutate()}>Save</button>
            </div>
          )}
        </div>
      )}

      {/* DRAFT / FAILED (Facebook) — manual fallback */}
      {(sl.status === 'DRAFT' || sl.status === 'FAILED') && sl.platform === 'facebook' && (
        <div style={{ padding: '8px 0 4px', display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          <a href={sl.action_url || 'https://www.facebook.com/marketplace/create/item'}
            target="_blank" rel="noreferrer" className="btn btn-secondary btn-sm">
            <ExternalLink size={12} /> Complete listing on Facebook
          </a>
          <button className="btn btn-secondary btn-sm"
            onClick={() => setEditingUrl(v => !v)}>
            <Link size={12} /> Enter listing URL
          </button>
        </div>
      )}
      {(sl.status === 'DRAFT' || sl.status === 'FAILED') && sl.platform === 'facebook' && editingUrl && (
        <div style={{ marginTop: 4, display: 'flex', gap: 6 }}>
          <input type="text" value={urlForm.platform_url}
            placeholder="https://www.facebook.com/marketplace/item/..."
            onChange={e => setUrlForm({ platform_url: e.target.value })}
            style={{ flex: 1, fontSize: 12 }} />
          <button className="btn btn-success btn-sm"
            disabled={!urlForm.platform_url || updateUrlMut.isPending}
            onClick={() => updateUrlMut.mutate()}>Save</button>
        </div>
      )}

      {/* POSTED — show link + actions */}
      {sl.status === 'POSTED' && (
        <div style={{ padding: '6px 0', display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
          {sl.platform_url && (
            <a href={sl.platform_url} target="_blank" rel="noreferrer"
              className="btn btn-secondary btn-sm">
              <ExternalLink size={12} /> View listing
            </a>
          )}
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            Listed {sl.listed_at ? new Date(sl.listed_at).toLocaleDateString() : ''}
          </span>
        </div>
      )}

      {/* Mark as sold form */}
      {markingSold && (
        <div className="sell-listing-sold-form">
          <div className="grid-2">
            <div className="form-group" style={{ margin: 0 }}>
              <label style={{ fontSize: 11 }}>Sale price</label>
              <input type="number" step="0.01" value={soldForm.sale_price}
                onChange={e => setSoldForm({ ...soldForm, sale_price: e.target.value })}
                placeholder={fmtMoney(sl.listed_price)} />
            </div>
            <div className="form-group" style={{ margin: 0 }}>
              <label style={{ fontSize: 11 }}>
                Platform fees
                <span className="label-hint" style={{ fontSize: 10, marginLeft: 4 }}>
                  est. ${estFee}
                </span>
              </label>
              <input type="number" step="0.01" value={soldForm.platform_fees}
                onChange={e => setSoldForm({ ...soldForm, platform_fees: e.target.value })}
                placeholder={`auto (${(pm.fee * 100).toFixed(1)}%)`} />
            </div>
          </div>
          <div className="grid-2" style={{ marginTop: 6 }}>
            <div className="form-group" style={{ margin: 0 }}>
              <label style={{ fontSize: 11 }}>Shipping cost</label>
              <input type="number" step="0.01" value={soldForm.shipping_cost}
                onChange={e => setSoldForm({ ...soldForm, shipping_cost: e.target.value })}
                placeholder="0.00" />
            </div>
            <div className="form-group" style={{ margin: 0 }}>
              <label style={{ fontSize: 11 }}>{pm.label} listing ID / URL <span className="label-hint">optional</span></label>
              <input type="text" value={soldForm.platform_url}
                onChange={e => setSoldForm({ ...soldForm, platform_url: e.target.value })}
                placeholder="optional" />
            </div>
          </div>
          <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
            <button className="btn btn-secondary btn-sm" onClick={() => setMarkingSold(false)}>Cancel</button>
            <button className="btn btn-success btn-sm"
              disabled={!soldForm.sale_price || soldMut.isPending}
              onClick={() => soldMut.mutate()}>
              {soldMut.isPending ? 'Saving…' : 'Confirm sale'}
            </button>
          </div>
        </div>
      )}

      {/* Footer actions */}
      {!markingSold && sl.status !== 'SOLD' && sl.status !== 'REMOVED' && (
        <div className="sell-listing-actions">
          {['POSTED', 'DRAFT'].includes(sl.status) && (
            <button className="btn btn-success btn-sm" onClick={() => setMarkingSold(true)}>
              <CheckCircle size={12} /> Mark as sold
            </button>
          )}
          <button className="btn btn-secondary btn-sm"
            onClick={() => { if (confirm('Remove this listing record?')) removeMut.mutate() }}>
            <Trash2 size={12} /> Remove
          </button>
        </div>
      )}
    </div>
  )
}

function SellListingsPanel({ item }) {
  const qc = useQueryClient()
  const [listingPlatform, setListingPlatform] = useState(null) // null | 'ebay' | 'facebook'
  const [price, setPrice] = useState(item.listed_price || '')

  const { data: sellListings = [], isLoading } = useQuery({
    queryKey: ['sell-listings', item.id],
    queryFn: () => getSellListings(item.id),
    // Poll every 4s if any listing is in POSTING state
    refetchInterval: (query) => {
      const data = query.state.data || []
      return data.some(sl => sl.status === 'POSTING') ? 4000 : false
    },
  })

  const createMut = useMutation({
    mutationFn: (platform) => createSellListing(item.id, {
      platform,
      listed_price: parseFloat(price),
    }),
    onSuccess: () => {
      setListingPlatform(null)
      qc.invalidateQueries({ queryKey: ['sell-listings', item.id] })
      qc.invalidateQueries({ queryKey: ['inventory', item.id] })
    },
  })

  const activePlatforms = new Set(
    sellListings.filter(sl => !['REMOVED'].includes(sl.status)).map(sl => sl.platform)
  )

  return (
    <div className="sell-listings-panel">
      {/* Platform buttons */}
      <div className="sell-listings-buttons">
        {['ebay', 'facebook'].map(p => {
          const pm = PLATFORM_META[p]
          const hasActive = activePlatforms.has(p)
          return (
            <button
              key={p}
              className={`btn btn-platform${listingPlatform === p ? ' active' : ''}`}
              style={{ '--platform-color': pm.color }}
              disabled={hasActive}
              title={hasActive ? `Already have an active ${pm.label} listing` : `List on ${pm.label}`}
              onClick={() => {
                if (!price) setPrice(item.listed_price || item.price_suggestion?.suggested_price || '')
                setListingPlatform(listingPlatform === p ? null : p)
              }}
            >
              <ShoppingBag size={12} />
              {hasActive ? `${pm.label} ✓` : `List on ${pm.label}`}
            </button>
          )
        })}
      </div>

      {/* Inline listing form */}
      {listingPlatform && (
        <div className="sell-listings-form">
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8 }}>
            {listingPlatform === 'ebay'
              ? 'Creates a draft with a pre-filled eBay listing form link.'
              : 'Playwright will fill your Facebook Marketplace listing automatically. Falls back to manual if selectors break.'}
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
            <div className="form-group" style={{ margin: 0, flex: 1 }}>
              <label style={{ fontSize: 11 }}>List price</label>
              <input type="number" step="0.01" value={price}
                onChange={e => setPrice(e.target.value)} placeholder="0.00" autoFocus />
            </div>
            <button className="btn btn-success"
              disabled={!price || createMut.isPending}
              onClick={() => createMut.mutate(listingPlatform)}>
              {createMut.isPending
                ? (listingPlatform === 'facebook' ? 'Starting…' : 'Creating…')
                : `List on ${PLATFORM_META[listingPlatform].label}`}
            </button>
            <button className="btn btn-secondary" onClick={() => setListingPlatform(null)}>
              <X size={14} />
            </button>
          </div>
        </div>
      )}

      {/* Existing listings */}
      {isLoading && <div className="loading" style={{ padding: '8px 0' }}>Loading…</div>}
      {sellListings.length === 0 && !isLoading && !listingPlatform && (
        <div style={{ fontSize: 12, color: 'var(--text-muted)', padding: '8px 0' }}>
          No listings yet. Use the buttons above to list this item.
        </div>
      )}
      {sellListings.map(sl => (
        <SellListingCard key={sl.id} sl={sl} itemId={item.id} item={item} />
      ))}
    </div>
  )
}

// ─── Item detail drawer ──────────────────────────────────────

function ItemDetailDrawer({ itemId, onClose }) {
  const qc = useQueryClient()
  const fileRef = useRef()
  const [error, setError] = useState(null)
  const [dragOver, setDragOver] = useState(false)

  const { data: item, isLoading } = useQuery({
    queryKey: ['inventory', itemId],
    queryFn: () => getInventoryItem(itemId),
  })

  const [form, setForm] = useState(null)
  useEffect(() => {
    if (item && !form) {
      setForm({
        title: item.title || '',
        description: item.description || '',
        category: item.category || '',
        condition: item.condition || 'GOOD',
        purchase_price: item.purchase_price ?? '',
        listed_price: item.listed_price ?? '',
        notes: item.notes || '',
        status: item.status || 'DRAFT',
      })
    }
  }, [item])

  const updateMut = useMutation({
    mutationFn: () => updateInventoryItem(itemId, {
      ...form,
      purchase_price: form.purchase_price === '' ? null : parseFloat(form.purchase_price),
      listed_price: form.listed_price === '' ? null : parseFloat(form.listed_price),
      category: form.category || null,
    }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['inventory', itemId] }),
    onError: (e) => setError(e?.response?.data?.detail || e.message),
  })

  const uploadMut = useMutation({
    mutationFn: (files) => uploadInventoryPhotos(itemId, files),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['inventory', itemId] }),
    onError: (e) => setError(e?.response?.data?.detail || e.message),
  })

  const deletePhotoMut = useMutation({
    mutationFn: (photoId) => deleteInventoryPhoto(photoId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['inventory', itemId] }),
  })

  const deleteItemMut = useMutation({
    mutationFn: () => deleteInventoryItem(itemId),
    onSuccess: () => onClose(),
  })

  function handleFiles(fileList) {
    const files = Array.from(fileList).filter(f => f.type.startsWith('image/'))
    if (files.length === 0) return
    uploadMut.mutate(files)
  }

  return (
    <>
      <div className="drawer-overlay" onClick={onClose} />
      <aside className="drawer" style={{ width: 700 }}>
        <div className="drawer-header">
          <div className="modal-title">{item?.title || 'Loading…'}</div>
          <button className="btn btn-secondary btn-sm" onClick={onClose}><X size={14} /></button>
        </div>
        <div className="drawer-body">
          {isLoading && <div className="loading">Loading…</div>}
          {error && <div className="error-box">{error}</div>}
          {item && form && (
            <>
              {/* Photos */}
              <div className="form-section">
                <div className="form-section-title">Photos</div>
                <div className={`photo-dropzone${dragOver ? ' drag-over' : ''}`}
                  onClick={() => fileRef.current?.click()}
                  onDragOver={e => { e.preventDefault(); setDragOver(true) }}
                  onDragLeave={() => setDragOver(false)}
                  onDrop={e => { e.preventDefault(); setDragOver(false); handleFiles(e.dataTransfer.files) }}>
                  <Upload size={20} style={{ marginBottom: 6 }} />
                  <div>{uploadMut.isPending ? 'Uploading…' : 'Drop photos here or click to upload'}</div>
                  <div style={{ fontSize: 11, marginTop: 4 }}>JPG, PNG, WebP — up to 15MB each</div>
                </div>
                <input ref={fileRef} type="file" accept="image/*" multiple style={{ display: 'none' }}
                  onChange={e => { handleFiles(e.target.files); e.target.value = '' }} />
                {item.photos.length > 0 && (
                  <div className="photo-thumb-grid">
                    {item.photos.map(p => (
                      <div key={p.id} className="photo-thumb">
                        <img src={inventoryPhotoUrl(p)} alt="" />
                        <button className="photo-thumb-remove"
                          onClick={() => deletePhotoMut.mutate(p.id)} title="Remove photo">×</button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Details */}
              <div className="form-section">
                <div className="form-section-title">Details</div>
                <div className="form-group">
                  <label>Title</label>
                  <input type="text" value={form.title}
                    onChange={e => setForm({ ...form, title: e.target.value })} />
                </div>
                <div className="grid-2">
                  <div className="form-group">
                    <label>Condition</label>
                    <select value={form.condition} onChange={e => setForm({ ...form, condition: e.target.value })}>
                      {CONDITIONS.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
                    </select>
                  </div>
                  <div className="form-group">
                    <label>Status</label>
                    <select value={form.status} onChange={e => setForm({ ...form, status: e.target.value })}>
                      {STATUSES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
                    </select>
                  </div>
                </div>
                <div className="grid-2">
                  <div className="form-group">
                    <label>Purchase price</label>
                    <input type="number" step="0.01" value={form.purchase_price}
                      onChange={e => setForm({ ...form, purchase_price: e.target.value })}
                      placeholder="What you paid" />
                  </div>
                  <div className="form-group">
                    <label>
                      Target sell price
                      {item.price_suggestion?.suggested_price && (
                        <span className="label-hint" style={{ marginLeft: 6 }}>
                          suggested {fmtMoney(item.price_suggestion.suggested_price)}
                        </span>
                      )}
                    </label>
                    <input type="number" step="0.01" value={form.listed_price}
                      onChange={e => setForm({ ...form, listed_price: e.target.value })}
                      placeholder="What you want to sell for" />
                  </div>
                </div>
                <div className="form-group">
                  <label>Category</label>
                  <input type="text" value={form.category}
                    onChange={e => setForm({ ...form, category: e.target.value })} />
                </div>
                <div className="form-group">
                  <label>Description</label>
                  <textarea value={form.description}
                    onChange={e => setForm({ ...form, description: e.target.value })} />
                </div>
                <div className="form-group">
                  <label>Internal notes</label>
                  <textarea value={form.notes}
                    onChange={e => setForm({ ...form, notes: e.target.value })} />
                </div>
              </div>

              {/* Auto-price */}
              <div className="form-section">
                <div className="form-section-title">Pricing</div>
                <AutoPricePanel item={item}
                  onUseSuggestedPrice={(p) => setForm(f => ({ ...f, listed_price: p }))} />
              </div>

              {/* Sell listings */}
              <div className="form-section">
                <div className="form-section-title">List on marketplaces</div>
                <SellListingsPanel item={item} />
              </div>

              {item.source_listing_id && (
                <div className="form-section">
                  <div className="field-hint">
                    Promoted from buy-side listing #{item.source_listing_id}.
                  </div>
                </div>
              )}
            </>
          )}
        </div>
        <div className="drawer-footer">
          <button className="btn btn-danger btn-sm"
            onClick={() => { if (confirm('Delete this item and its photos? This cannot be undone.')) deleteItemMut.mutate() }}>
            <Trash2 size={12} /> Delete
          </button>
          <div style={{ flex: 1 }} />
          <button className="btn btn-secondary" onClick={onClose}>Close</button>
          <button className="btn btn-success" disabled={!form || updateMut.isPending}
            onClick={() => { setError(null); updateMut.mutate() }}>
            {updateMut.isPending ? 'Saving…' : 'Save changes'}
          </button>
        </div>
      </aside>
    </>
  )
}
