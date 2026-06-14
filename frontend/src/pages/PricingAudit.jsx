import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import {
  Microscope, Cpu, ShoppingCart, Sliders, Play, ChevronDown, ChevronRight,
  CheckCircle2, XCircle, AlertTriangle, Search,
} from 'lucide-react'
import {
  getPricingStatus, getPricingComps, getPricingTrace, diagnosePricing,
} from '../api'

// ── formatters ───────────────────────────────────────────────────────────────
function fmtMoney(v) {
  if (v == null) return '—'
  return `$${Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`
}
function fmtDateTime(dt) {
  if (!dt) return 'never'
  return new Date(dt.endsWith('Z') ? dt : dt + 'Z').toLocaleString()
}
function fmtAgo(dt) {
  if (!dt) return 'never'
  const ms = Date.now() - new Date(dt.endsWith('Z') ? dt : dt + 'Z').getTime()
  const m = Math.round(ms / 60000)
  if (m < 1) return 'just now'
  if (m < 60) return `${m}m ago`
  const h = Math.round(m / 60)
  if (h < 24) return `${h}h ago`
  return `${Math.round(h / 24)}d ago`
}
const CONF_BADGE = { high: 'badge-green', medium: 'badge-yellow', low: 'badge-gray' }

function Dot({ ok, warn }) {
  const color = ok ? 'var(--green)' : warn ? 'var(--yellow)' : 'var(--red)'
  return (
    <span style={{
      display: 'inline-block', width: 9, height: 9, borderRadius: '50%',
      background: color, boxShadow: `0 0 8px ${color}`, flexShrink: 0,
    }} />
  )
}

// ── status strip ───────────────────────────────────────────────────────────────
function StatusStrip() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['pricing-status'],
    queryFn: getPricingStatus,
    refetchInterval: 15_000,
  })

  if (isLoading) return <div className="loading">Probing pricing pipeline…</div>
  if (error) return <div className="error-box">Couldn't reach backend: {error.message}</div>

  const o = data.ollama || {}
  const e = data.ebay
  const c = data.config || {}
  const ollamaWarn = o.reachable && (!o.maker_present || (c.local_llm_checker_enabled && !o.checker_present))

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 14, marginBottom: 20 }}>
      {/* Ollama / local AI */}
      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
          <Cpu size={15} color="var(--accent)" />
          <strong>Local AI (Ollama)</strong>
          <span style={{ marginLeft: 'auto' }}><Dot ok={o.reachable && !ollamaWarn} warn={ollamaWarn} /></span>
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>{o.base_url}</div>
        {!o.reachable ? (
          <div className="badge badge-red">offline — {o.error?.slice(0, 60) || 'unreachable'}</div>
        ) : (
          <>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, marginBottom: 8 }}>
              {o.models?.length ? o.models.map(m => (
                <span key={m} className="badge badge-gray" style={{ fontSize: 10 }}>{m}</span>
              )) : <span className="text-muted" style={{ fontSize: 12 }}>no models pulled</span>}
            </div>
            <div style={{ fontSize: 12, display: 'flex', flexDirection: 'column', gap: 3 }}>
              <span>{o.maker_present ? '✓' : '✗'} maker <strong>{o.maker_model}</strong></span>
              {c.local_llm_checker_enabled
                ? <span>{o.checker_present ? '✓' : '✗'} checker <strong>{o.checker_model}</strong></span>
                : <span className="text-muted">checker disabled</span>}
            </div>
          </>
        )}
      </div>

      {/* eBay comps */}
      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
          <ShoppingCart size={15} color="var(--accent)" />
          <strong>eBay sold comps</strong>
          <span style={{ marginLeft: 'auto' }}><Dot ok={e?.enabled && e?.status === 'healthy'} warn={e?.enabled && e?.status !== 'healthy'} /></span>
        </div>
        {!e ? <div className="text-muted" style={{ fontSize: 12 }}>No eBay source configured.</div> : (
          <div style={{ fontSize: 12, display: 'flex', flexDirection: 'column', gap: 4 }}>
            <span>{e.enabled ? '✓ enabled' : '✗ disabled'} · <span className={`badge badge-${e.status === 'healthy' ? 'green' : 'orange'}`}>{e.status || 'unknown'}</span></span>
            <span className="text-muted">last success: {fmtAgo(e.last_success_at)}</span>
            <span className="text-muted">last run: {fmtAgo(e.last_run_at)}</span>
            {e.last_error && <span style={{ color: 'var(--red)' }}>{e.last_error.slice(0, 70)}</span>}
          </div>
        )}
      </div>

      {/* Config + cache */}
      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
          <Sliders size={15} color="var(--accent)" />
          <strong>Pricing config</strong>
        </div>
        <div style={{ fontSize: 12, display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span>AI gap-fill: {c.local_llm_pricing_enabled ? <span className="badge badge-green">on</span> : <span className="badge badge-gray">off</span>}</span>
          <span>agreement tolerance: <strong>{Math.round((c.local_llm_agreement_tolerance ?? 0.25) * 100)}%</strong></span>
          {data.cache?.map(cs => (
            <span key={cs.source} className="text-muted">
              cache <strong style={{ color: 'var(--text)' }}>{cs.source}</strong>: {cs.fresh}/{cs.total} fresh · {fmtAgo(cs.newest_fetched_at)}
            </span>
          ))}
          {!data.cache?.length && <span className="text-muted">comp cache empty</span>}
        </div>
      </div>
    </div>
  )
}

// ── one model's response card (maker / checker) ─────────────────────────────────
function ModelCard({ role, m }) {
  const [open, setOpen] = useState(false)
  if (!m) return null
  const accent = role === 'maker' ? 'var(--accent)' : 'var(--orange)'
  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 12, borderTop: `2px solid ${accent}` }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
        <span style={{ textTransform: 'uppercase', fontSize: 11, letterSpacing: 0.5, color: accent, fontWeight: 700 }}>{role}</span>
        <span className="text-muted" style={{ fontSize: 11 }}>{m.model || '—'}</span>
        {m.latency_ms != null && <span className="text-muted" style={{ fontSize: 11, marginLeft: 'auto' }}>{(m.latency_ms / 1000).toFixed(1)}s</span>}
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 8 }}>
        <strong style={{ fontSize: 22 }}>{m.value != null ? fmtMoney(m.value) : '—'}</strong>
        {m.confidence && <span className={`badge ${CONF_BADGE[m.confidence] || 'badge-gray'}`}>{m.confidence}</span>}
      </div>
      {m.error && <div style={{ fontSize: 12, color: 'var(--red)', marginBottom: 6 }}>⚠ {m.error}</div>}
      {(m.raw_response || m.prompt) && (
        <button className="btn btn-sm btn-secondary" onClick={() => setOpen(o => !o)} style={{ fontSize: 11 }}>
          {open ? <ChevronDown size={11} /> : <ChevronRight size={11} />} raw response
        </button>
      )}
      {open && (
        <div style={{ marginTop: 8 }}>
          {m.raw_response && (
            <>
              <div className="text-muted" style={{ fontSize: 11, marginBottom: 3 }}>model output</div>
              <pre style={{ fontSize: 11, background: 'var(--bg)', padding: 10, borderRadius: 6, overflowX: 'auto', color: 'var(--text)', margin: 0 }}>{m.raw_response}</pre>
            </>
          )}
          {m.prompt && (
            <>
              <div className="text-muted" style={{ fontSize: 11, margin: '8px 0 3px' }}>prompt sent</div>
              <pre style={{ fontSize: 11, background: 'var(--bg)', padding: 10, borderRadius: 6, overflowX: 'auto', color: 'var(--text-muted)', margin: 0, whiteSpace: 'pre-wrap' }}>{m.prompt}</pre>
            </>
          )}
        </div>
      )}
    </div>
  )
}

// Verdict bar shared by live diagnosis and stored breakdowns.
function Verdict({ b }) {
  if (!b) return null
  const agreePct = b.agreement != null ? Math.round(b.agreement * 100) : null
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 12 }}>
      <span className="text-muted" style={{ fontSize: 12 }}>final</span>
      <strong style={{ fontSize: 20 }}>{fmtMoney(b.final_value)}</strong>
      {b.confidence && <span className={`badge ${CONF_BADGE[b.confidence] || 'badge-gray'}`}>{b.confidence} conf</span>}
      {b.needs_review
        ? <span className="badge badge-red"><AlertTriangle size={11} style={{ verticalAlign: -1 }} /> needs review</span>
        : b.final_value != null && <span className="badge badge-green"><CheckCircle2 size={11} style={{ verticalAlign: -1 }} /> agree</span>}
      {agreePct != null && (
        <span style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
          <span className="text-muted">agreement</span>
          <span style={{ width: 90, height: 6, background: 'var(--surface2)', borderRadius: 3, overflow: 'hidden' }}>
            <span style={{ display: 'block', height: '100%', width: `${agreePct}%`, background: agreePct >= 75 ? 'var(--green)' : 'var(--yellow)' }} />
          </span>
          <strong>{agreePct}%</strong>
        </span>
      )}
    </div>
  )
}

// ── live diagnosis ───────────────────────────────────────────────────────────
function LiveDiagnosis() {
  const [keyword, setKeyword] = useState('')
  const [category, setCategory] = useState('')
  const mut = useMutation({ mutationFn: diagnosePricing })
  const run = () => keyword.trim() && mut.mutate({ keyword: keyword.trim(), category: category.trim() || null })
  const b = mut.data
  const CATS = ['furniture', 'grills', 'espresso', 'monitor', 'tools', 'sonos', 'apparel']

  return (
    <div className="card" style={{ marginBottom: 20 }}>
      <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Play size={14} color="var(--accent)" /> Live diagnosis — re-query both models now
      </div>
      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12 }}>
        Bypasses the cache and asks both qwen models live. Confirms the AI pricing path is online and shows exactly what each model returns.
      </div>
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end', marginBottom: 8 }}>
        <div style={{ flex: '1 1 240px' }}>
          <label>Item (keyword)</label>
          <input value={keyword} onChange={e => setKeyword(e.target.value)} placeholder="Weber Genesis II E-310"
            onKeyDown={e => e.key === 'Enter' && run()} />
        </div>
        <div style={{ flex: '0 1 180px' }}>
          <label>Category (optional)</label>
          <input value={category} onChange={e => setCategory(e.target.value)} placeholder="furniture" list="audit-cats" />
          <datalist id="audit-cats">{CATS.map(c => <option key={c} value={c} />)}</datalist>
        </div>
        <button className="btn btn-primary" onClick={run} disabled={mut.isPending || !keyword.trim()}>
          {mut.isPending ? 'Asking models…' : 'Run diagnosis'}
        </button>
      </div>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 4 }}>
        {CATS.map(c => (
          <button key={c} className="btn btn-sm btn-secondary" style={{ fontSize: 11 }} onClick={() => setCategory(c)}>{c}</button>
        ))}
      </div>

      {mut.isError && <div className="error-box" style={{ marginTop: 12 }}>{mut.error.message}</div>}
      {b && (
        <div style={{ marginTop: 16, borderTop: '1px solid var(--border)', paddingTop: 14 }}>
          {b.error && !b.final_value && <div className="error-box" style={{ marginBottom: 12 }}>No estimate: {b.error}</div>}
          <Verdict b={b} />
          <div className="grid-2">
            <ModelCard role="maker" m={b.maker} />
            <ModelCard role="checker" m={b.checker} />
          </div>
        </div>
      )}
    </div>
  )
}

// ── decision ladder ─────────────────────────────────────────────────────────
function DecisionLadder({ steps }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {steps.map(s => {
        const state = s.won ? 'won' : s.eligible ? 'eligible' : 'skipped'
        const color = state === 'won' ? 'var(--green)' : state === 'eligible' ? 'var(--text)' : 'var(--text-muted)'
        return (
          <div key={s.name} style={{
            display: 'flex', alignItems: 'center', gap: 10, padding: '8px 12px', borderRadius: 6,
            background: s.won ? 'rgba(34,197,94,0.10)' : 'var(--surface2)',
            border: s.won ? '1px solid rgba(34,197,94,0.4)' : '1px solid var(--border)',
            opacity: state === 'skipped' ? 0.5 : 1,
          }}>
            {s.won ? <CheckCircle2 size={15} color="var(--green)" />
              : s.eligible ? <span style={{ width: 15, height: 15, borderRadius: '50%', border: '2px solid var(--text-muted)' }} />
              : <XCircle size={15} color="var(--text-muted)" />}
            <strong style={{ color, fontSize: 13 }}>{s.label}</strong>
            <span className="text-muted" style={{ fontSize: 11, marginLeft: 'auto' }}>
              {s.won ? '✓ used' : s.eligible ? 'eligible' : 'n/a for category'}
            </span>
            {s.note && s.won && <span className="text-muted" style={{ fontSize: 11 }}>· {s.note}</span>}
          </div>
        )
      })}
    </div>
  )
}

// ── per-listing trace ──────────────────────────────────────────────────────────
function ListingTrace({ listingId, onClear }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['pricing-trace', listingId],
    queryFn: () => getPricingTrace(listingId),
    enabled: !!listingId,
  })

  if (!listingId) return null
  if (isLoading) return <div className="card" style={{ marginBottom: 20 }}><div className="loading">Tracing listing #{listingId}…</div></div>
  if (error) return <div className="error-box" style={{ marginBottom: 20 }}>Trace failed: {error.message}</div>

  const s = data.score
  const b = s?.pricing_breakdown
  return (
    <div className="card" style={{ marginBottom: 20 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, marginBottom: 14 }}>
        {data.listing.image_url && <img src={data.listing.image_url} alt="" style={{ width: 64, height: 64, objectFit: 'cover', borderRadius: 6 }} />}
        <div style={{ flex: 1 }}>
          <div className="card-title" style={{ marginBottom: 2 }}>Trace · listing #{data.listing.id}</div>
          <div style={{ fontSize: 13 }}>
            {data.listing.url
              ? <a href={data.listing.url} target="_blank" rel="noreferrer" style={{ color: 'var(--accent)' }}>{data.listing.title}</a>
              : data.listing.title}
          </div>
          <div className="text-muted" style={{ fontSize: 12, marginTop: 3 }}>
            asking {fmtMoney(data.listing.price)} · {data.watchlist?.name || '—'}
            {data.watchlist?.category ? ` (${data.watchlist.category})` : ''} · keyword "{data.search_keyword}"
          </div>
        </div>
        <button className="btn btn-sm btn-secondary" onClick={onClear}>✕ close</button>
      </div>

      <div style={{ marginBottom: 16 }}>
        <div className="card-title">Decision path</div>
        <DecisionLadder steps={data.steps} />
      </div>

      {s ? (
        <div className="grid-2" style={{ fontSize: 13, marginBottom: 16 }}>
          <div><div className="text-muted">Rating</div><strong>{s.rating} · {s.score?.toFixed(0)}/100</strong></div>
          <div><div className="text-muted">Value source</div><strong>{s.value_source || '—'}{s.is_lead ? ' · 💬 lead' : ''}</strong></div>
          <div><div className="text-muted">Est. value</div><strong>{fmtMoney(s.estimated_value)}</strong></div>
          <div><div className="text-muted">Conservative</div><strong>{fmtMoney(s.conservative_value)}</strong></div>
          <div><div className="text-muted">Target buy</div><strong>{fmtMoney(s.target_buy_price)}</strong></div>
          <div><div className="text-muted">Est. profit</div><strong>{fmtMoney(s.estimated_profit)}</strong></div>
        </div>
      ) : <div className="text-muted" style={{ marginBottom: 16 }}>No score row for this listing.</div>}

      {b && (b.maker?.value != null || b.checker?.value != null || b.maker?.error || b.checker?.error) && (
        <div style={{ marginBottom: 16, borderTop: '1px solid var(--border)', paddingTop: 14 }}>
          <div className="card-title">🤖 Maker-checker (as priced at scrape time)</div>
          <Verdict b={b} />
          <div className="grid-2">
            <ModelCard role="maker" m={b.maker} />
            <ModelCard role="checker" m={b.checker} />
          </div>
          {b.maker && b.maker.raw_response == null && (
            <div className="text-muted" style={{ fontSize: 11, marginTop: 8 }}>
              Raw responses weren't captured for this listing (priced before audit logging). Re-scrape or use live diagnosis above to see them.
            </div>
          )}
        </div>
      )}

      {data.comps?.length > 0 && (
        <div style={{ borderTop: '1px solid var(--border)', paddingTop: 14 }}>
          <div className="card-title">Comp cache for "{data.search_keyword}"</div>
          <table style={{ fontSize: 12 }}>
            <thead><tr><th>Source</th><th>Median</th><th>Range</th><th>Samples</th><th>Fetched</th><th>Fresh</th></tr></thead>
            <tbody>
              {data.comps.map((c, i) => (
                <tr key={i}>
                  <td><span className="badge badge-blue">{c.source}</span></td>
                  <td>{fmtMoney(c.median_price)}</td>
                  <td className="text-muted">{fmtMoney(c.min_price)}–{fmtMoney(c.max_price)}</td>
                  <td>{c.sample_count}</td>
                  <td className="text-muted">{fmtAgo(c.fetched_at)}</td>
                  <td>{c.fresh ? <span className="badge badge-green">fresh</span> : <span className="badge badge-gray">stale</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── recent comps table ─────────────────────────────────────────────────────────
function CompRow({ c }) {
  const [open, setOpen] = useState(false)
  const hasDetail = c.details && (c.details.maker || c.details.checker)
  return (
    <>
      <tr style={{ cursor: hasDetail ? 'pointer' : 'default' }} onClick={() => hasDetail && setOpen(o => !o)}>
        <td>{hasDetail ? (open ? <ChevronDown size={12} /> : <ChevronRight size={12} />) : ''}</td>
        <td style={{ maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.keyword}</td>
        <td className="text-muted">{c.category || '—'}</td>
        <td><span className={`badge ${c.source === 'local_llm' ? 'badge-green' : 'badge-blue'}`}>{c.source}</span></td>
        <td><strong>{fmtMoney(c.median_price)}</strong></td>
        <td className="text-muted">{fmtMoney(c.min_price)}–{fmtMoney(c.max_price)}</td>
        <td>{c.sample_count}</td>
        <td className="text-muted">{fmtAgo(c.fetched_at)}</td>
        <td>{c.fresh ? <span className="badge badge-green">fresh</span> : <span className="badge badge-gray">stale</span>}</td>
      </tr>
      {open && hasDetail && (
        <tr>
          <td colSpan={9} style={{ background: 'var(--bg)', padding: 14 }}>
            <Verdict b={c.details} />
            <div className="grid-2">
              <ModelCard role="maker" m={c.details.maker} />
              <ModelCard role="checker" m={c.details.checker} />
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

function RecentComps() {
  const [source, setSource] = useState('')
  const [q, setQ] = useState('')
  const { data, isLoading } = useQuery({
    queryKey: ['pricing-comps', source],
    queryFn: () => getPricingComps({ source: source || undefined, limit: 150 }),
    refetchInterval: 30_000,
  })
  const rows = (data || []).filter(c => !q || c.keyword.toLowerCase().includes(q.toLowerCase()))

  return (
    <div className="card">
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12, flexWrap: 'wrap' }}>
        <div className="card-title" style={{ margin: 0 }}>Recent comps (last prices)</div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
          <div style={{ position: 'relative' }}>
            <Search size={13} style={{ position: 'absolute', left: 8, top: 9, color: 'var(--text-muted)' }} />
            <input value={q} onChange={e => setQ(e.target.value)} placeholder="filter keyword" style={{ paddingLeft: 26, height: 32 }} />
          </div>
          <select value={source} onChange={e => setSource(e.target.value)} style={{ height: 32 }}>
            <option value="">All sources</option>
            <option value="local_llm">Local AI</option>
            <option value="ebay">eBay</option>
            <option value="ebay_sold">eBay sold</option>
          </select>
        </div>
      </div>
      {isLoading ? <div className="loading">Loading comps…</div> : (
        <div className="table-wrap">
          <table>
            <thead><tr><th></th><th>Keyword</th><th>Category</th><th>Source</th><th>Median</th><th>Range</th><th>Samples</th><th>Fetched</th><th>Fresh</th></tr></thead>
            <tbody>
              {rows.map(c => <CompRow key={c.id} c={c} />)}
              {!rows.length && <tr><td colSpan={9} className="text-muted" style={{ textAlign: 'center', padding: 24 }}>No cached comps yet.</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── page ─────────────────────────────────────────────────────────────────────
export default function PricingAudit() {
  const [params, setParams] = useSearchParams()
  const listingParam = params.get('listing')
  const [lookup, setLookup] = useState('')

  const setListing = (id) => {
    if (id) setParams({ listing: String(id) })
    else setParams({})
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Microscope size={22} color="var(--accent)" /> Pricing Audit
          </div>
          <div className="page-subtitle">Trace how every value is derived — eBay comps, the decision path, and both qwen models' raw responses.</div>
        </div>
      </div>

      <StatusStrip />
      <LiveDiagnosis />

      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-title">Trace a listing</div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
          <div style={{ flex: '0 1 200px' }}>
            <label>Listing ID</label>
            <input value={lookup} onChange={e => setLookup(e.target.value)} placeholder="e.g. 1423"
              onKeyDown={e => e.key === 'Enter' && setListing(lookup.trim())} />
          </div>
          <button className="btn btn-primary" onClick={() => setListing(lookup.trim())} disabled={!lookup.trim()}>Trace</button>
          <span className="text-muted" style={{ fontSize: 12 }}>Tip: open the score modal on the Listings page and use “Open in Audit”.</span>
        </div>
      </div>

      {listingParam && <ListingTrace listingId={listingParam} onClear={() => setListing(null)} />}

      <RecentComps />
    </div>
  )
}
