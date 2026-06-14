import { useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Edit2, Trash2, MapPin, DollarSign, Clock, ToggleLeft, ToggleRight, Sparkles, ClipboardPaste, Camera, RefreshCw } from 'lucide-react'
import { getWatchlists, createWatchlist, updateWatchlist, deleteWatchlist, toggleWatchlist, getWebhooks, analyzePhoto } from '../api'

// ── Claude prompt builder ────────────────────────────────────────────── //
function buildClaudePrompt(description) {
  return `I'm building a deal-monitoring watchlist to find resale bargains for: "${description}"

People list these items on Facebook Marketplace, Craigslist, OfferUp, eBay, and Mercari.

Return ONLY a valid JSON object — no explanation, no markdown, no code fences. Just raw JSON with these exact fields:

{
  "name": "short watchlist name (2-4 words)",
  "keywords": ["exactly 5 search terms, ordered best-first — ONLY the first 5 are actually searched, so make each one a query a seller's listing would match (brand+model combos beat broad terms)"],
  "brands": ["top 5-10 brands worth tracking in this category"],
  "required_keywords": ["3-10 terms — a listing is DISCARDED unless its title/description contains at least one. Use this to lock in the specific subtype/brand/team the user asked for (e.g. 'propane' for gas grills, team names for sports gear). Leave empty [] only if the user truly wants everything in the category"],
  "negative_keywords": ["12-20 terms to exclude. Cover three buckets: (1) condition junk — broken, cracked, parts only, for parts, as is, as-is, untested, needs repair, repair, not working, doesn't work; (2) wrong subtypes the user did NOT ask for (e.g. charcoal/pellet/electric if they want propane); (3) off-brand/third-party accessory makers if the user wants OEM only"],
  "min_price": <realistic minimum price for a legit used unit, as integer>,
  "max_price": <realistic maximum price, or 99999 if highly variable, as integer>,
  "notes": "1-2 sentences on what makes a good deal and what red flags to watch for"
}

Pay close attention to qualifiers in my description ("only", "just", "working", specific brands/teams/fuel types) — encode them as required_keywords and negative_keywords, not just as search keywords.`
}

async function openInClaude(description) {
  const prompt = buildClaudePrompt(description)
  if (window.platapicker?.copyToClipboard) {
    await window.platapicker.copyToClipboard(prompt)
  } else {
    await navigator.clipboard.writeText(prompt)
  }
  const url = 'https://claude.ai/new'
  if (window.platapicker?.openExternal) {
    window.platapicker.openExternal(url)
  } else {
    window.open(url, '_blank')
  }
}

const SOURCES = ['facebook', 'auctionninja', 'craigslist', 'offerup', 'mercari', 'ebay']

const SOURCE_LABELS = {
  facebook: 'Facebook',
  auctionninja: 'AuctionNinja',
  craigslist: 'Craigslist',
  offerup: 'OfferUp',
  mercari: 'Mercari',
  ebay: 'eBay',
}

const EMPTY_FORM = {
  name: '', enabled: true, category: '',
  keywords: [], negative_keywords: [], required_keywords: [], brands: [], aliases: [],
  locations: ['10706'], radius_miles: 50,
  min_price: 0, max_price: 99999,
  sources_enabled: [], run_frequency_minutes: 60,
  min_rating_to_alert: 'GOOD', min_profit_margin: 0.20, min_profit_dollars: 50,
  estimated_shipping_cost: 0, sales_tax_rate: 0,
  discord_webhook_id: null, notes: '',
  auto_outreach_enabled: false,
  outreach_message_template: '',
  auto_list_on_buy: false,
}

// ── Claude AI Assistant Panel ────────────────────────────────────────── //
function ClaudeAssistant({ onApply }) {
  const [inputMode, setInputMode] = useState('text') // 'text' | 'photo'

  // text-mode state
  const [description, setDescription] = useState('')
  const [pasteText, setPasteText] = useState('')
  const [step, setStep] = useState('input') // 'input' | 'waiting' | 'paste'
  const [parseError, setParseError] = useState(null)

  // photo-mode state
  const [analyzing, setAnalyzing] = useState(false)
  const [photoError, setPhotoError] = useState(null)
  const photoRef = useRef()

  const handleGenerate = async () => {
    if (!description.trim()) return
    setStep('waiting')
    try {
      await openInClaude(description.trim())
      setStep('paste')
    } catch {
      setStep('paste')
    }
  }

  const handleImport = () => {
    setParseError(null)
    let text = pasteText.trim()
    text = text.replace(/^```json\s*/i, '').replace(/^```\s*/i, '').replace(/```\s*$/i, '').trim()
    try {
      const data = JSON.parse(text)
      const result = {
        name: data.name || '',
        keywords: Array.isArray(data.keywords) ? data.keywords : [],
        brands: Array.isArray(data.brands) ? data.brands : [],
        required_keywords: Array.isArray(data.required_keywords) ? data.required_keywords : [],
        negative_keywords: Array.isArray(data.negative_keywords) ? data.negative_keywords : [],
        min_price: typeof data.min_price === 'number' ? data.min_price : 0,
        max_price: typeof data.max_price === 'number' ? data.max_price : 99999,
        notes: data.notes || '',
      }
      onApply(result)
      setStep('input')
      setDescription('')
      setPasteText('')
    } catch {
      setParseError('Could not parse the response. Make sure you copied the full JSON from Claude.')
    }
  }

  async function handlePhotoFill(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setAnalyzing(true)
    setPhotoError(null)
    try {
      const data = await analyzePhoto(file, 'watchlist')
      const usable = data && typeof data === 'object'
        && (data.name || (Array.isArray(data.keywords) && data.keywords.length))
      if (!usable) {
        setPhotoError('Claude could not extract anything useful from that photo — try a clearer shot.')
        return
      }
      onApply({
        name: data.name || '',
        keywords: Array.isArray(data.keywords) ? data.keywords : [],
        brands: Array.isArray(data.brands) ? data.brands : [],
        required_keywords: Array.isArray(data.required_keywords) ? data.required_keywords : [],
        negative_keywords: Array.isArray(data.negative_keywords) ? data.negative_keywords : [],
        min_price: typeof data.min_price === 'number' ? data.min_price : 0,
        max_price: typeof data.max_price === 'number' ? data.max_price : 99999,
        notes: data.notes || '',
      })
    } catch (err) {
      setPhotoError(err?.response?.data?.detail || 'Photo analysis failed. Check your Claude API key in Settings.')
    } finally {
      setAnalyzing(false)
      e.target.value = ''
    }
  }

  return (
    <div className="claude-assistant">
      <div className="claude-assistant-header" style={{ justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Sparkles size={14} style={{ color: 'var(--accent)' }} />
          <span>Generate with Claude <span className="claude-badge">Free</span></span>
        </div>
        <div style={{ display: 'flex', gap: 4 }}>
          <button
            type="button"
            className={`btn btn-sm ${inputMode === 'text' ? 'btn-accent' : 'btn-secondary'}`}
            style={{ padding: '2px 8px', fontSize: 11 }}
            onClick={() => setInputMode('text')}
          >Text</button>
          <button
            type="button"
            className={`btn btn-sm ${inputMode === 'photo' ? 'btn-accent' : 'btn-secondary'}`}
            style={{ padding: '2px 8px', fontSize: 11 }}
            onClick={() => setInputMode('photo')}
          ><Camera size={11} style={{ marginRight: 3 }} />Photo</button>
        </div>
      </div>

      {inputMode === 'text' && (
        <>
          {step === 'input' && (
            <div className="claude-input-row">
              <input
                type="text"
                className="claude-desc-input"
                placeholder="Describe what you're looking for… e.g. ultrawide monitor, vintage turntable"
                value={description}
                onChange={e => setDescription(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleGenerate()}
              />
              <button
                type="button"
                className="btn btn-accent btn-sm"
                onClick={handleGenerate}
                disabled={!description.trim()}
              >
                Open Claude →
              </button>
            </div>
          )}

          {step === 'waiting' && (
            <div className="claude-step">
              <div className="claude-step-text">
                ✅ Prompt copied to clipboard — paste it into Claude, then copy the JSON response it gives you.
              </div>
              <button type="button" className="btn btn-sm btn-secondary" onClick={() => setStep('paste')}>
                <ClipboardPaste size={13} /> I have the response
              </button>
            </div>
          )}

          {step === 'paste' && (
            <div className="claude-paste-area">
              <div className="claude-step-text" style={{ marginBottom: 8 }}>
                ✅ Prompt copied — paste Claude's JSON response below:
              </div>
              {parseError && <div className="claude-error">{parseError}</div>}
              <textarea
                className="claude-paste-input"
                placeholder="Paste Claude's JSON response here…"
                value={pasteText}
                onChange={e => setPasteText(e.target.value)}
                rows={5}
              />
              <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  onClick={handleImport}
                  disabled={!pasteText.trim()}
                >
                  Apply to Form
                </button>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => { setStep('input'); setParseError(null); setPasteText('') }}
                >
                  Start Over
                </button>
              </div>
            </div>
          )}
        </>
      )}

      {inputMode === 'photo' && (
        <div>
          {photoError && <div className="claude-error" style={{ marginBottom: 8 }}>{photoError}</div>}
          <input
            ref={photoRef}
            type="file"
            accept="image/*"
            style={{ display: 'none' }}
            onChange={handlePhotoFill}
          />
          <button
            type="button"
            className="btn btn-accent btn-sm"
            onClick={() => photoRef.current?.click()}
            disabled={analyzing}
            style={{ width: '100%' }}
          >
            {analyzing
              ? <><RefreshCw size={13} className="spin" /> Analyzing photo…</>
              : <><Camera size={13} /> Upload a photo — Claude fills the form</>}
          </button>
          <div className="claude-step-text" style={{ marginTop: 8, fontSize: 11, color: 'var(--text-muted)' }}>
            Upload a photo of the item you want to flip. Claude will suggest keywords, price range, and search terms.
          </div>
        </div>
      )}
    </div>
  )
}

// ── Chip input ───────────────────────────────────────────────────────── //
function ChipInput({ value = [], onChange, placeholder }) {
  const [input, setInput] = useState('')
  const wrapRef = useRef()
  const inputRef = useRef()

  const add = (raw) => {
    const trimmed = (raw || input).trim().replace(/,$/, '')
    if (trimmed && !value.includes(trimmed)) onChange([...value, trimmed])
    setInput('')
  }

  const remove = (chip) => onChange(value.filter(c => c !== chip))

  return (
    <div
      className="chip-input-wrap"
      ref={wrapRef}
      onClick={() => inputRef.current?.focus()}
    >
      {value.map(c => (
        <span key={c} className="chip">
          {c}
          <button
            type="button"
            className="chip-remove"
            onMouseDown={e => { e.preventDefault(); remove(c) }}
          >×</button>
        </span>
      ))}
      <input
        ref={inputRef}
        className="chip-input-field"
        value={input}
        onChange={e => setInput(e.target.value)}
        onKeyDown={e => {
          if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); add() }
          if (e.key === 'Backspace' && !input && value.length) remove(value[value.length - 1])
        }}
        onBlur={() => { if (input.trim()) add() }}
        placeholder={value.length === 0 ? placeholder : ''}
      />
    </div>
  )
}

// ── Source toggles ───────────────────────────────────────────────────── //
function SourceToggles({ value, onChange }) {
  const allOn = !value || value.length === 0

  const toggle = (name) => {
    if (allOn) {
      onChange(SOURCES.filter(s => s !== name))
    } else if (value.includes(name)) {
      const next = value.filter(s => s !== name)
      onChange(next.length === 0 ? SOURCES.filter(s => s !== name) : next)
    } else {
      const next = [...value, name]
      onChange(next.length === SOURCES.length ? [] : next)
    }
  }

  const isActive = (name) => allOn || value.includes(name)

  return (
    <div className="source-pills">
      {SOURCES.map(s => (
        <button
          key={s}
          type="button"
          className={`source-pill${isActive(s) ? ' active' : ''}`}
          onClick={() => toggle(s)}
        >
          {isActive(s) ? '✓ ' : ''}{SOURCE_LABELS[s]}
        </button>
      ))}
    </div>
  )
}

// ── Drawer ───────────────────────────────────────────────────────────── //
function WatchlistDrawer({ initial, webhooks, onClose, onSave }) {
  const [form, setForm] = useState(() =>
    initial
      ? { ...EMPTY_FORM, ...initial, locations: initial.locations || [] }
      : { ...EMPTY_FORM }
  )
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const applyClaudeResult = (data) => {
    setForm(f => ({
      ...f,
      name: data.name || f.name,
      keywords: data.keywords?.length ? data.keywords : f.keywords,
      brands: data.brands?.length ? data.brands : f.brands,
      required_keywords: data.required_keywords?.length ? data.required_keywords : f.required_keywords,
      negative_keywords: data.negative_keywords?.length ? data.negative_keywords : f.negative_keywords,
      min_price: data.min_price ?? f.min_price,
      max_price: data.max_price ?? f.max_price,
      notes: data.notes || f.notes,
    }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.name.trim()) { setError('Name is required'); return }
    setSaving(true)
    setError(null)
    try {
      await onSave(form)
      onClose()
    } catch (err) {
      setError(err?.response?.data?.detail || String(err))
    } finally {
      setSaving(false)
    }
  }

  const locationVal = Array.isArray(form.locations)
    ? (form.locations[0] || '')
    : (form.locations || '')

  return (
    <>
      <div className="drawer-overlay" onClick={onClose} />
      <div className="drawer">
        <div className="drawer-header">
          <div>
            <div style={{ fontWeight: 700, fontSize: 17 }}>
              {initial ? 'Edit Watchlist' : 'New Watchlist'}
            </div>
            {initial && (
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
                {initial.name}
              </div>
            )}
          </div>
          <button className="btn btn-secondary btn-sm" onClick={onClose}>✕</button>
        </div>

        <div className="drawer-body">
          {error && <div className="error-box">{error}</div>}

          {!initial && (
            <ClaudeAssistant onApply={applyClaudeResult} />
          )}

          <form id="wl-form" onSubmit={handleSubmit}>

            {/* BASICS */}
            <div className="form-section">
              <div className="form-section-title">Basics</div>
              <div className="grid-2">
                <div className="form-group">
                  <label>Name *</label>
                  <input
                    type="text"
                    value={form.name}
                    onChange={e => set('name', e.target.value)}
                    placeholder="e.g. Espresso Machines"
                    autoFocus
                  />
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
            </div>

            {/* KEYWORDS */}
            <div className="form-section">
              <div className="form-section-title">Keywords</div>
              <div className="form-group">
                <label>
                  Search Keywords
                  <span className="label-hint">press Enter or comma to add</span>
                </label>
                <ChipInput
                  value={Array.isArray(form.keywords) ? form.keywords : []}
                  onChange={v => set('keywords', v)}
                  placeholder="Type a keyword and press Enter…"
                />
              </div>
              <div className="form-group">
                <label>
                  Must Include
                  <span className="label-hint">listing kept only if title/description has one of these</span>
                </label>
                <ChipInput
                  value={Array.isArray(form.required_keywords) ? form.required_keywords : []}
                  onChange={v => set('required_keywords', v)}
                  placeholder="Miami, Redhawks, MU…"
                />
              </div>
              <div className="form-group">
                <label>
                  Exclude Keywords
                  <span className="label-hint">listings with these are skipped</span>
                </label>
                <ChipInput
                  value={Array.isArray(form.negative_keywords) ? form.negative_keywords : []}
                  onChange={v => set('negative_keywords', v)}
                  placeholder="broken, parts only…"
                />
              </div>
              <div className="form-group">
                <label>Brands to Prioritize</label>
                <ChipInput
                  value={Array.isArray(form.brands) ? form.brands : []}
                  onChange={v => set('brands', v)}
                  placeholder="La Marzocco, Rancilio…"
                />
              </div>
            </div>

            {/* LOCATION */}
            <div className="form-section">
              <div className="form-section-title">Location &amp; Distance</div>
              <div className="form-group">
                <label>Search Location</label>
                <input
                  type="text"
                  value={locationVal}
                  onChange={e => set('locations', e.target.value ? [e.target.value] : [])}
                  placeholder="New York, NY · Los Angeles, CA · Chicago, IL"
                />
                <div className="field-hint">Used for Facebook Marketplace and Craigslist</div>
              </div>
              <div className="form-group">
                <label>Search Radius — <span style={{ color: 'var(--accent)', fontWeight: 700 }}>{form.radius_miles} miles</span></label>
                <input
                  type="range"
                  className="range-input"
                  min={5} max={200} step={5}
                  value={form.radius_miles}
                  onChange={e => set('radius_miles', +e.target.value)}
                />
                <div className="range-labels">
                  <span>5 mi</span><span>50 mi</span><span>100 mi</span><span>200 mi</span>
                </div>
              </div>
            </div>

            {/* PRICE */}
            <div className="form-section">
              <div className="form-section-title">Price Range</div>
              <div className="grid-2">
                <div className="form-group">
                  <label>Min Price ($)</label>
                  <input
                    type="number" min={0}
                    value={form.min_price}
                    onChange={e => set('min_price', +e.target.value)}
                    placeholder="0"
                  />
                </div>
                <div className="form-group">
                  <label>Max Price ($)</label>
                  <input
                    type="number" min={0}
                    value={form.max_price >= 99999 ? '' : form.max_price}
                    onChange={e => set('max_price', e.target.value ? +e.target.value : 99999)}
                    placeholder="No limit"
                  />
                </div>
              </div>
            </div>

            {/* SOURCES */}
            <div className="form-section">
              <div className="form-section-title">Sources</div>
              <div className="form-group">
                <label>Search On</label>
                <SourceToggles
                  value={Array.isArray(form.sources_enabled) ? form.sources_enabled : []}
                  onChange={v => set('sources_enabled', v)}
                />
                <div className="field-hint">All selected by default — deselect to restrict</div>
              </div>
              <div className="form-group">
                <label>Check Every</label>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                  {[15, 30, 60, 120, 240].map(m => (
                    <button
                      key={m}
                      type="button"
                      className={`btn btn-sm${form.run_frequency_minutes === m ? ' btn-primary' : ' btn-secondary'}`}
                      onClick={() => set('run_frequency_minutes', m)}
                    >
                      {m < 60 ? `${m}m` : `${m / 60}h`}
                    </button>
                  ))}
                  <span className="text-muted" style={{ fontSize: 12 }}>or</span>
                  <input
                    type="number" min={15}
                    value={form.run_frequency_minutes}
                    onChange={e => set('run_frequency_minutes', +e.target.value)}
                    style={{ width: 70 }}
                  />
                  <span className="text-muted" style={{ fontSize: 12 }}>min</span>
                </div>
              </div>
            </div>

            {/* SCORING */}
            <div className="form-section">
              <div className="form-section-title">Scoring</div>
              <div className="grid-2">
                <div className="form-group">
                  <label>Shipping cost (sell-side)</label>
                  <input
                    type="number" step="0.01" min={0}
                    value={form.estimated_shipping_cost}
                    onChange={e => set('estimated_shipping_cost', +e.target.value)}
                    placeholder="0.00"
                  />
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
                    What you pay to ship to buyers (e.g. $12 for eBay, $0 for local pickup).
                  </div>
                </div>
                <div className="form-group">
                  <label>Sales tax rate (buy-side)</label>
                  <input
                    type="number" step="0.001" min={0} max={0.2}
                    value={form.sales_tax_rate}
                    onChange={e => set('sales_tax_rate', +e.target.value)}
                    placeholder="0.00"
                  />
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
                    Tax on your purchase (e.g. 0.08 for 8%). Leave 0 for local cash buys.
                  </div>
                </div>
              </div>
            </div>

            {/* ALERTS */}
            <div className="form-section">
              <div className="form-section-title">Alerts</div>
              <div className="grid-2">
                <div className="form-group">
                  <label>Alert When Rating ≥</label>
                  <select value={form.min_rating_to_alert} onChange={e => set('min_rating_to_alert', e.target.value)}>
                    <option value="STEAL">🔥 STEAL only</option>
                    <option value="GREAT">⭐ GREAT or better</option>
                    <option value="GOOD">✅ GOOD or better</option>
                    <option value="FAIR">🟡 FAIR or better</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>Discord Webhook</label>
                  <select
                    value={form.discord_webhook_id || ''}
                    onChange={e => set('discord_webhook_id', e.target.value ? +e.target.value : null)}
                  >
                    <option value="">None</option>
                    {webhooks?.map(wh => (
                      <option key={wh.id} value={wh.id}>{wh.name}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="grid-2">
                <div className="form-group">
                  <label>Min Profit Margin</label>
                  <input
                    type="number" step="0.01" min={0} max={1}
                    value={form.min_profit_margin}
                    onChange={e => set('min_profit_margin', +e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label>Min Profit ($)</label>
                  <input
                    type="number" min={0}
                    value={form.min_profit_dollars}
                    onChange={e => set('min_profit_dollars', +e.target.value)}
                  />
                </div>
              </div>
            </div>

            {/* AUTOMATION */}
            <div className="form-section">
              <div className="form-section-title">Automation</div>

              <div className="form-group" style={{ marginBottom: 14 }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={form.auto_outreach_enabled}
                    onChange={e => set('auto_outreach_enabled', e.target.checked)}
                  />
                  <span style={{ fontWeight: 600 }}>Auto-message sellers on Facebook</span>
                </label>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4, marginLeft: 24 }}>
                  When a qualifying deal is found, automatically send a message to the seller via
                  your existing Facebook session. Rate limited to 15 messages/hour.
                </div>
              </div>

              {form.auto_outreach_enabled && (
                <div className="form-group" style={{ marginBottom: 14 }}>
                  <label>Message template</label>
                  <textarea
                    value={form.outreach_message_template}
                    onChange={e => set('outreach_message_template', e.target.value)}
                    placeholder={`Hi! Is {title} still available? I can pick it up today for cash. Please let me know — thanks!`}
                    style={{ minHeight: 70, fontFamily: 'monospace', fontSize: 12 }}
                  />
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
                    Use <code style={{ background: 'var(--bg-2)', padding: '1px 4px', borderRadius: 3 }}>{'{title}'}</code> and <code style={{ background: 'var(--bg-2)', padding: '1px 4px', borderRadius: 3 }}>{'{url}'}</code> as placeholders. Leave blank for default message.
                  </div>
                </div>
              )}

              <div className="form-group" style={{ marginBottom: 4 }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={form.auto_list_on_buy}
                    onChange={e => set('auto_list_on_buy', e.target.checked)}
                  />
                  <span style={{ fontWeight: 600 }}>Auto-list on Facebook after purchase</span>
                </label>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4, marginLeft: 24 }}>
                  When you use "Full Pipeline" on a listing, it will automatically price the item
                  and create a Facebook Marketplace listing without additional clicks.
                </div>
              </div>
            </div>

            {/* NOTES */}
            <div className="form-section">
              <div className="form-section-title">Notes</div>
              <textarea
                value={form.notes}
                onChange={e => set('notes', e.target.value)}
                placeholder="Anything to remember about this watchlist…"
                style={{ minHeight: 60 }}
              />
            </div>

          </form>
        </div>

        <div className="drawer-footer">
          <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button type="submit" form="wl-form" className="btn btn-primary" disabled={saving}>
            {saving ? 'Saving…' : initial ? 'Save Changes' : 'Create Watchlist'}
          </button>
        </div>
      </div>
    </>
  )
}

// ── Watchlist card ───────────────────────────────────────────────────── //
function WatchlistCard({ wl, onEdit, onDelete, onToggle }) {
  const activeSources = wl.sources_enabled?.length ? wl.sources_enabled : SOURCES
  const location = wl.locations?.[0] || null
  const priceLabel = wl.max_price >= 99999
    ? `$${wl.min_price}+`
    : `$${wl.min_price} – $${wl.max_price}`
  const freqLabel = wl.run_frequency_minutes < 60
    ? `${wl.run_frequency_minutes}m`
    : `${wl.run_frequency_minutes / 60}h`

  return (
    <div className={`wl-card${!wl.enabled ? ' disabled' : ''}`}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          {/* Title row */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6, flexWrap: 'wrap' }}>
            <span style={{ fontWeight: 700, fontSize: 15 }}>{wl.name}</span>
            {wl.category && <span className="badge badge-blue">{wl.category}</span>}
            {wl.enabled
              ? <span className="badge badge-green">Active</span>
              : <span className="badge badge-gray">Paused</span>}
            {wl.auto_outreach_enabled && (
              <span className="badge" style={{ background: 'rgba(245,158,11,0.15)', color: '#f59e0b', border: '1px solid rgba(245,158,11,0.3)', fontSize: 10 }}>
                ✉ Auto-message
              </span>
            )}
            {wl.auto_list_on_buy && (
              <span className="badge" style={{ background: 'rgba(34,197,94,0.12)', color: 'var(--green)', border: '1px solid rgba(34,197,94,0.25)', fontSize: 10 }}>
                ⚡ Auto-list
              </span>
            )}
          </div>

          {/* Meta row */}
          <div className="wl-meta">
            {location && (
              <span className="wl-meta-item">
                <MapPin size={11} />
                {location} · {wl.radius_miles}mi
              </span>
            )}
            <span className="wl-meta-item">
              <DollarSign size={11} />
              {priceLabel}
            </span>
            <span className="wl-meta-item">
              <Clock size={11} />
              every {freqLabel}
            </span>
            <span className="wl-meta-item">
              alert: <strong style={{ color: 'var(--text)', marginLeft: 2 }}>{wl.min_rating_to_alert}+</strong>
            </span>
          </div>

          {/* Keywords */}
          {wl.keywords?.length > 0 && (
            <div className="tag-list" style={{ marginBottom: 8 }}>
              {wl.keywords.slice(0, 7).map(k => (
                <span key={k} className="tag">{k}</span>
              ))}
              {wl.keywords.length > 7 && (
                <span className="text-muted" style={{ fontSize: 11 }}>
                  +{wl.keywords.length - 7} more
                </span>
              )}
            </div>
          )}

          {/* Active sources */}
          <div className="wl-sources">
            {activeSources.map(s => (
              <span key={s} className="source-tag">{SOURCE_LABELS[s] || s}</span>
            ))}
          </div>
        </div>

        {/* Action buttons */}
        <div className="actions-row" style={{ flexShrink: 0 }}>
          <button className="btn btn-sm btn-secondary" title="Edit" onClick={() => onEdit(wl)}>
            <Edit2 size={13} />
          </button>
          <button
            className="btn btn-sm btn-secondary"
            title={wl.enabled ? 'Pause' : 'Resume'}
            onClick={() => onToggle(wl.id)}
          >
            {wl.enabled
              ? <ToggleRight size={14} color="var(--green)" />
              : <ToggleLeft size={14} />}
          </button>
          <button
            className="btn btn-sm btn-danger"
            title="Delete"
            onClick={() => window.confirm(`Delete "${wl.name}"?`) && onDelete(wl.id)}
          >
            <Trash2 size={13} />
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Page ─────────────────────────────────────────────────────────────── //
export default function Watchlists() {
  const qc = useQueryClient()
  const [drawer, setDrawer] = useState(null)

  const { data: watchlists = [], isLoading } = useQuery({
    queryKey: ['watchlists'],
    queryFn: getWatchlists,
  })
  const { data: webhooks = [] } = useQuery({
    queryKey: ['webhooks'],
    queryFn: getWebhooks,
  })

  const createMut = useMutation({
    mutationFn: createWatchlist,
    onSuccess: () => qc.invalidateQueries(['watchlists']),
  })
  const updateMut = useMutation({
    mutationFn: ({ id, data }) => updateWatchlist(id, data),
    onSuccess: () => qc.invalidateQueries(['watchlists']),
  })
  const deleteMut = useMutation({
    mutationFn: deleteWatchlist,
    onSuccess: () => qc.invalidateQueries(['watchlists']),
  })
  const toggleMut = useMutation({
    mutationFn: toggleWatchlist,
    onSuccess: () => qc.invalidateQueries(['watchlists']),
  })

  const handleSave = (data) =>
    drawer?.mode === 'edit'
      ? updateMut.mutateAsync({ id: drawer.watchlist.id, data })
      : createMut.mutateAsync(data)

  const activeCount = watchlists.filter(w => w.enabled).length
  const pausedCount = watchlists.filter(w => !w.enabled).length

  if (isLoading) return <div className="loading">Loading watchlists…</div>

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Watchlists</div>
          <div className="page-subtitle">
            {watchlists.length === 0
              ? 'No watchlists yet — create one to start monitoring deals.'
              : `${activeCount} active · ${pausedCount} paused`}
          </div>
        </div>
        <button className="btn btn-primary" onClick={() => setDrawer({ mode: 'create' })}>
          <Plus size={14} /> New Watchlist
        </button>
      </div>

      {drawer && (
        <WatchlistDrawer
          initial={drawer.mode === 'edit' ? drawer.watchlist : undefined}
          webhooks={webhooks}
          onClose={() => setDrawer(null)}
          onSave={handleSave}
        />
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {watchlists.map(wl => (
          <WatchlistCard
            key={wl.id}
            wl={wl}
            onEdit={w => setDrawer({ mode: 'edit', watchlist: w })}
            onDelete={id => deleteMut.mutate(id)}
            onToggle={id => toggleMut.mutate(id)}
          />
        ))}

        {!watchlists.length && (
          <div className="empty-state">
            <div className="icon">📋</div>
            <div style={{ marginBottom: 16 }}>
              Create a watchlist to tell Platapicker what products to look for.
            </div>
            <button
              className="btn btn-primary"
              onClick={() => setDrawer({ mode: 'create' })}
            >
              <Plus size={14} /> Create your first watchlist
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
