import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { EyeOff, Eye, Send, ExternalLink, Info, Bot, Package, MessageCircle, Zap } from 'lucide-react'
import { useNavigate, Link } from 'react-router-dom'
import { getListings, ignoreListing, unignoreListing, sendDiscord, getListingRaw, getWatchlists, triggerClaudeReview, promoteListingToInventory, sendListingOutreach, runFullPipeline } from '../api'

function RatingBadge({ rating }) {
  if (!rating) return <span className="text-muted">—</span>
  return <span className={`rating-${rating}`}>{rating}</span>
}

function fmtMoney(v) {
  if (v == null) return '—'
  return `$${Number(v).toLocaleString()}`
}

function fmtDate(dt) {
  if (!dt) return '—'
  return new Date(dt + 'Z').toLocaleDateString()
}

function fmtPct(v) {
  if (v == null) return '—'
  return `${Number(v).toFixed(0)}%`
}

// Color a 0-100 score: green ≥70, yellow ≥40, gray below.
function scoreColor(score) {
  if (score == null) return 'var(--text-muted)'
  if (score >= 70) return 'var(--green)'
  if (score >= 40) return 'var(--yellow)'
  return 'var(--text-muted)'
}

const RISK_BADGE = { LOW: 'badge-green', MEDIUM: 'badge-yellow', HIGH: 'badge-red' }
const CONF_BADGE = { HIGH: 'badge-green', MEDIUM: 'badge-yellow', LOW: 'badge-gray' }

// Where the estimated value came from — shown as a labelled badge.
const VALUE_SOURCE_META = {
  ebay:         { label: '🛒 eBay sold comps',  cls: 'badge-blue' },
  maker_checker:{ label: '🤖 AI Maker-Checker', cls: 'badge-green' },
  local_llm:    { label: '🤖 Local AI',         cls: 'badge-green' },
  table:        { label: '📋 Price table',      cls: 'badge-gray' },
  gamecube:     { label: '🎮 GameCube prices',  cls: 'badge-gray' },
}

function ValueSourceBadge({ score }) {
  const meta = VALUE_SOURCE_META[score?.value_source]
  if (!meta) return null
  return <span className={`badge ${meta.cls}`} style={{ fontSize: 11 }}>{meta.label}</span>
}

// Full maker-checker breakdown: both models' numbers, agreement, and the verdict.
function MakerCheckerPanel({ score }) {
  const pb = score?.pricing_breakdown
  if (!pb || (pb.maker?.value == null && pb.checker?.value == null)) return null
  const agreePct = pb.agreement != null ? `${Math.round(pb.agreement * 100)}%` : '—'
  return (
    <div style={{ marginBottom: 12, borderTop: '1px solid var(--border)', paddingTop: 12 }}>
      <div className="card-title">🤖 Maker-Checker Pricing</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10, flexWrap: 'wrap' }}>
        <strong style={{ fontSize: 20 }}>{fmtMoney(pb.final_value)}</strong>
        {pb.confidence && <span className={`badge ${CONF_BADGE[pb.confidence?.toUpperCase()] || 'badge-gray'}`}>{pb.confidence} conf</span>}
        {pb.needs_review
          ? <span className="badge badge-red" title="The two models disagreed; using the lower estimate.">⚠️ needs review</span>
          : <span className="badge badge-green">✓ agree</span>}
        <span className="text-muted" style={{ fontSize: 12 }}>agreement {agreePct}</span>
      </div>
      <div className="grid-2" style={{ fontSize: 13 }}>
        <div>
          <div className="text-muted">Maker</div>
          <strong>{fmtMoney(pb.maker?.value)}</strong>
          <div className="text-muted" style={{ fontSize: 11 }}>{pb.maker?.model || '—'} · {pb.maker?.confidence || '—'}</div>
        </div>
        <div>
          <div className="text-muted">Checker</div>
          <strong>{fmtMoney(pb.checker?.value)}</strong>
          <div className="text-muted" style={{ fontSize: 11 }}>{pb.checker?.model || '—'} · {pb.checker?.confidence || '—'}</div>
        </div>
      </div>
      {pb.needs_review && (
        <div style={{ fontSize: 12, marginTop: 8, color: 'var(--orange)' }}>
          → Models disagreed by more than the tolerance; using the lower estimate to avoid a false deal.
        </div>
      )}
    </div>
  )
}

// Compact at-a-glance Net Flip cell: ⚡score · ROI · net$
function NetFlipBadge({ score }) {
  if (!score || score.net_flip_score == null) return <span className="text-muted">—</span>
  const nf = score.net_flip_score
  return (
    <span
      title={`Net Flip ${nf}/100 · ROI ${fmtPct(score.estimated_roi_percent)} · net ${fmtMoney(score.net_profit)} · risk ${score.risk_level || '—'}`}
      style={{ cursor: 'help', whiteSpace: 'nowrap' }}
    >
      <strong style={{ color: scoreColor(nf), fontSize: 14 }}>⚡{nf}</strong>
      <span className="text-muted" style={{ fontSize: 11, marginLeft: 4 }}>
        {fmtPct(score.estimated_roi_percent)}
      </span>
    </span>
  )
}

// Small inline signal badges (bundle / underpriced) shown under the title.
function SignalBadges({ listing }) {
  const score = listing.deal_score
  const bundle = score?.bundle
  const bad = score?.bad_listing
  const showBundle = bundle?.is_bundle
  const showUnder = bad?.bad_listing_good_item
  const showModel = listing.detected_model
  const showLead = score?.is_lead
  if (!showBundle && !showUnder && !showModel && !showLead) return null
  return (
    <div style={{ display: 'flex', gap: 4, marginTop: 3, flexWrap: 'wrap' }}>
      {showLead && (
        <span className="badge badge-green" title="No fixed price (best offer / $0) — flagged by resale value. Verify the actual price." style={{ fontSize: 10, cursor: 'help' }}>
          💬 Lead{score.conservative_value != null ? ` ~${fmtMoney(score.conservative_value)}` : ''}
        </span>
      )}
      {showUnder && (
        <span className="badge badge-orange" title={bad.suggested_reason} style={{ fontSize: 10, cursor: 'help' }}>
          🔎 Underpriced {bad.undervaluation_score}
        </span>
      )}
      {showBundle && (
        <span className="badge badge-blue" title={bundle.liquidation_plan} style={{ fontSize: 10, cursor: 'help' }}>
          🧩 Bundle {fmtMoney(bundle.estimated_bundle_resale_total)}
        </span>
      )}
      {showModel && (
        <span className="badge badge-gray" title={`Detected from photo: ${listing.detected_brand || ''} ${listing.detected_model}`} style={{ fontSize: 10, cursor: 'help' }}>
          📷 {listing.detected_model}
        </span>
      )}
    </div>
  )
}

function RawModal({ id, onClose }) {
  const { data, isLoading } = useQuery({
    queryKey: ['listing-raw', id],
    queryFn: () => getListingRaw(id),
  })
  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={{ maxWidth: 700 }}>
        <div className="modal-header">
          <div className="modal-title">Raw Payload #{id}</div>
          <button className="btn btn-secondary btn-sm" onClick={onClose}>✕</button>
        </div>
        {isLoading ? <div className="loading">Loading...</div> : (
          <pre style={{ fontSize: 12, overflowX: 'auto', background: 'var(--bg)', padding: 12, borderRadius: 6, color: 'var(--text-muted)' }}>
            {JSON.stringify(data, null, 2)}
          </pre>
        )}
      </div>
    </div>
  )
}

function ClaudeReviewBadge({ review, listingId, onTrigger }) {
  if (!review) {
    return (
      <button
        className="btn btn-sm btn-secondary"
        title="Run Claude review"
        onClick={() => onTrigger(listingId)}
        style={{ fontSize: 11, padding: '2px 6px' }}
      >
        <Bot size={11} /> Ask
      </button>
    )
  }
  if (review.error && !review.summary) {
    return <span className="badge badge-gray" title={review.error}>Error</span>
  }
  const color = review.approved ? 'badge-green' : 'badge-red'
  const icon = review.approved ? '✓' : '✗'
  const label = review.approved ? 'OK' : 'Flag'
  return (
    <span
      className={`badge ${color}`}
      title={[
        review.summary,
        review.flags?.length ? `⚠ ${review.flags.join(', ')}` : '',
        review.positives?.length ? `✓ ${review.positives.join(', ')}` : '',
        review.photo_notes || '',
      ].filter(Boolean).join('\n')}
      style={{ cursor: 'help' }}
    >
      {icon} {label}
    </span>
  )
}

function ClaudeModal({ listing, onClose }) {
  const review = listing.claude_review
  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={{ maxWidth: 480 }}>
        <div className="modal-header">
          <div className="modal-title">🤖 Claude Review — {listing.title.slice(0, 40)}</div>
          <button className="btn btn-secondary btn-sm" onClick={onClose}>✕</button>
        </div>
        {!review ? (
          <div className="text-muted">No Claude review available yet.</div>
        ) : (
          <>
            <div style={{ marginBottom: 12 }}>
              <span className={`badge ${review.approved ? 'badge-green' : 'badge-red'}`} style={{ marginRight: 8 }}>
                {review.approved ? '✓ Approved' : '✗ Flagged'}
              </span>
              <span className="text-muted" style={{ fontSize: 12 }}>
                {(review.confidence * 100).toFixed(0)}% confidence · {review.model}
              </span>
            </div>
            {review.summary && (
              <div style={{ fontSize: 13, marginBottom: 12, fontStyle: 'italic' }}>
                "{review.summary}"
              </div>
            )}
            {review.positives?.length > 0 && (
              <div style={{ marginBottom: 8 }}>
                <div className="card-title">✅ Positives</div>
                <ul style={{ listStyle: 'none', padding: 0 }}>
                  {review.positives.map((p, i) => (
                    <li key={i} style={{ fontSize: 13, marginBottom: 4, color: 'var(--green)' }}>✓ {p}</li>
                  ))}
                </ul>
              </div>
            )}
            {review.flags?.length > 0 && (
              <div style={{ marginBottom: 8 }}>
                <div className="card-title">⚠️ Flags</div>
                <ul style={{ listStyle: 'none', padding: 0 }}>
                  {review.flags.map((f, i) => (
                    <li key={i} style={{ fontSize: 13, marginBottom: 4, color: 'var(--yellow)' }}>⚠ {f}</li>
                  ))}
                </ul>
              </div>
            )}
            {review.photo_notes && (
              <div>
                <div className="card-title">📷 Photo Notes</div>
                <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>{review.photo_notes}</div>
              </div>
            )}
            {review.error && (
              <div className="error-box" style={{ marginTop: 8, fontSize: 12 }}>Error: {review.error}</div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function ScoreModal({ listing, onClose }) {
  const score = listing.deal_score
  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={{ maxWidth: 500, maxHeight: '85vh', overflowY: 'auto' }}>
        <div className="modal-header">
          <div className="modal-title">Deal Score — {listing.title.slice(0, 40)}</div>
          <div style={{ display: 'flex', gap: 6 }}>
            <Link to={`/pricing-audit?listing=${listing.id}`} className="btn btn-secondary btn-sm" title="Open full pricing trace in the audit tool" style={{ textDecoration: 'none' }}>
              🔬 Audit
            </Link>
            <button className="btn btn-secondary btn-sm" onClick={onClose}>✕</button>
          </div>
        </div>
        {!score ? <div className="text-muted">No score available.</div> : (
          <>
            <div style={{ marginBottom: 16 }}>
              <RatingBadge rating={score.rating} />
              <span style={{ marginLeft: 8, fontSize: 18, fontWeight: 700 }}>{score.score?.toFixed(0)}/100</span>
            </div>
            <div style={{ marginBottom: 10 }}><ValueSourceBadge score={score} /></div>
            <div className="grid-2" style={{ marginBottom: 12, fontSize: 13 }}>
              <div><div className="text-muted">Est. Value</div><strong>{fmtMoney(score.estimated_value)}</strong></div>
              <div><div className="text-muted">Conservative</div><strong>{fmtMoney(score.conservative_value)}</strong></div>
              <div><div className="text-muted">Target Buy</div><strong>{fmtMoney(score.target_buy_price)}</strong></div>
              <div><div className="text-muted">Est. Profit</div><strong>{fmtMoney(score.estimated_profit)}</strong></div>
              <div><div className="text-muted">Profit Margin</div><strong>{score.profit_margin != null ? `${(score.profit_margin * 100).toFixed(0)}%` : '—'}</strong></div>
              <div><div className="text-muted">Confidence</div><strong>{score.confidence != null ? `${(score.confidence * 100).toFixed(0)}%` : '—'}</strong></div>
            </div>
            {score.reasons?.length > 0 && (
              <div style={{ marginBottom: 12 }}>
                <div className="card-title">Reasons</div>
                <ul style={{ listStyle: 'none', padding: 0 }}>
                  {score.reasons.map((r, i) => <li key={i} style={{ fontSize: 13, marginBottom: 4 }}>✅ {r}</li>)}
                </ul>
              </div>
            )}
            {score.warnings?.length > 0 && (
              <div style={{ marginBottom: 12 }}>
                <div className="card-title">Warnings</div>
                <ul style={{ listStyle: 'none', padding: 0 }}>
                  {score.warnings.map((w, i) => <li key={i} style={{ fontSize: 13, marginBottom: 4, color: 'var(--yellow)' }}>⚠️ {w}</li>)}
                </ul>
              </div>
            )}

            {/* ── Maker-Checker Pricing ────────────────────────────────── */}
            <MakerCheckerPanel score={score} />

            {/* ── Net Flip Score ───────────────────────────────────────── */}
            {score.net_flip_score != null && (
              <div style={{ marginBottom: 12, borderTop: '1px solid var(--border)', paddingTop: 12 }}>
                <div className="card-title">💰 Net Flip Score</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                  <strong style={{ fontSize: 22, color: scoreColor(score.net_flip_score) }}>⚡{score.net_flip_score}</strong>
                  <span className="text-muted" style={{ fontSize: 12 }}>/ 100</span>
                  {score.risk_level && <span className={`badge ${RISK_BADGE[score.risk_level] || 'badge-gray'}`}>risk {score.risk_level}</span>}
                  {score.confidence_label && <span className={`badge ${CONF_BADGE[score.confidence_label] || 'badge-gray'}`}>{score.confidence_label} conf</span>}
                </div>
                <div className="grid-2" style={{ fontSize: 13, marginBottom: 8 }}>
                  <div><div className="text-muted">Est. Resale</div><strong>{fmtMoney(score.net_flip?.estimated_resale_price)}</strong></div>
                  <div><div className="text-muted">Net Profit</div><strong style={{ color: score.net_profit >= 0 ? 'var(--green)' : 'var(--red)' }}>{fmtMoney(score.net_profit)}</strong></div>
                  <div><div className="text-muted">ROI</div><strong>{fmtPct(score.estimated_roi_percent)}</strong></div>
                  <div><div className="text-muted">Fees</div><strong>{fmtMoney(score.net_flip?.estimated_fees)}</strong></div>
                  <div><div className="text-muted">Shipping</div><strong>{fmtMoney(score.net_flip?.estimated_shipping_cost)}</strong></div>
                  <div><div className="text-muted">Repair</div><strong>{fmtMoney(score.net_flip?.estimated_repair_cost)}</strong></div>
                </div>
                {score.net_flip?.score_reasons?.length > 0 && (
                  <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                    {score.net_flip.score_reasons.map((r, i) => (
                      <li key={i} style={{ fontSize: 12, marginBottom: 3, color: 'var(--text-muted)' }}>• {r}</li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            {/* ── Bad Listing / Undervaluation ─────────────────────────── */}
            {score.bad_listing?.bad_listing_good_item && (
              <div style={{ marginBottom: 12, borderTop: '1px solid var(--border)', paddingTop: 12 }}>
                <div className="card-title">🔎 Possibly Underpriced ({score.bad_listing.undervaluation_score})</div>
                {score.bad_listing.suggested_reason && (
                  <div style={{ fontSize: 13, marginBottom: 6, fontStyle: 'italic' }}>{score.bad_listing.suggested_reason}</div>
                )}
                <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                  {score.bad_listing.detected_signals?.map((s, i) => (
                    <li key={i} style={{ fontSize: 13, marginBottom: 3, color: 'var(--orange)' }}>→ {s}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* ── Bundle Arbitrage ─────────────────────────────────────── */}
            {score.bundle?.is_bundle && (
              <div style={{ marginBottom: 12, borderTop: '1px solid var(--border)', paddingTop: 12 }}>
                <div className="card-title">🧩 Bundle — {score.bundle.recommended_strategy}</div>
                <div className="grid-2" style={{ fontSize: 13, marginBottom: 8 }}>
                  <div><div className="text-muted">Resale Total</div><strong>{fmtMoney(score.bundle.estimated_bundle_resale_total)}</strong></div>
                  <div><div className="text-muted">Net if Split</div><strong style={{ color: score.bundle.estimated_bundle_net_profit >= 0 ? 'var(--green)' : 'var(--red)' }}>{fmtMoney(score.bundle.estimated_bundle_net_profit)}</strong></div>
                </div>
                {score.bundle.liquidation_plan && (
                  <div style={{ fontSize: 12, marginBottom: 8, color: 'var(--text-muted)' }}>{score.bundle.liquidation_plan}</div>
                )}
                {score.bundle.bundle_items?.length > 0 && (
                  <table style={{ width: '100%', fontSize: 12 }}>
                    <tbody>
                      {score.bundle.bundle_items.map((it, i) => (
                        <tr key={i}>
                          <td style={{ padding: '2px 0' }}>{it.item}</td>
                          <td style={{ textAlign: 'right', color: 'var(--text-muted)' }}>{it.confidence}</td>
                          <td style={{ textAlign: 'right', fontWeight: 600 }}>{fmtMoney(it.estimated_resale_price)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}

            {/* ── Photo Analysis ───────────────────────────────────────── */}
            {listing.photo_analysis && (
              <div style={{ borderTop: '1px solid var(--border)', paddingTop: 12 }}>
                <div className="card-title">📷 Photo Analysis</div>
                <div style={{ fontSize: 13, marginBottom: 6 }}>
                  {listing.detected_brand && <span style={{ marginRight: 10 }}><span className="text-muted">Brand:</span> <strong>{listing.detected_brand}</strong></span>}
                  {listing.detected_model && <span><span className="text-muted">Model:</span> <strong>{listing.detected_model}</strong></span>}
                </div>
                {listing.photo_analysis.detected_condition_issues?.length > 0 && (
                  <div style={{ fontSize: 12, color: 'var(--yellow)', marginBottom: 4 }}>
                    Issues: {listing.photo_analysis.detected_condition_issues.join(', ')}
                  </div>
                )}
                {listing.photo_analysis.detected_accessories?.length > 0 && (
                  <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                    Accessories: {listing.photo_analysis.detected_accessories.join(', ')}
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

export default function Listings() {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [filters, setFilters] = useState({ source: '', watchlist_id: '', rating: '', ignored: false })
  const [rawModal, setRawModal] = useState(null)
  const [scoreModal, setScoreModal] = useState(null)
  const [claudeModal, setClaudeModal] = useState(null)
  const [msg, setMsg] = useState(null)

  const { data: listings, isLoading } = useQuery({
    queryKey: ['listings', filters],
    queryFn: () => getListings({
      source: filters.source || undefined,
      watchlist_id: filters.watchlist_id || undefined,
      rating: filters.rating || undefined,
      ignored: filters.ignored,
      limit: 100,
    }),
    refetchInterval: 60_000,
  })

  const { data: watchlists } = useQuery({ queryKey: ['watchlists'], queryFn: getWatchlists })

  const ignoreMut = useMutation({
    mutationFn: ignoreListing,
    onSuccess: () => qc.invalidateQueries(['listings']),
  })
  const unignoreMut = useMutation({
    mutationFn: unignoreListing,
    onSuccess: () => qc.invalidateQueries(['listings']),
  })
  const discordMut = useMutation({
    mutationFn: sendDiscord,
    onSuccess: () => { setMsg('✅ Sent to Discord!'); qc.invalidateQueries(['listings']) },
    onError: (e) => setMsg(`❌ ${e?.response?.data?.detail || e.message}`),
  })

  const claudeMut = useMutation({
    mutationFn: triggerClaudeReview,
    onSuccess: (_, id) => {
      setMsg('🤖 Claude review queued — refresh in a moment.')
      setTimeout(() => qc.invalidateQueries(['listings']), 3000)
    },
    onError: (e) => setMsg(`❌ ${e?.response?.data?.detail || e.message}`),
  })

  const promoteMut = useMutation({
    mutationFn: promoteListingToInventory,
    onSuccess: (item) => {
      setMsg(`✅ Added "${item.title}" to inventory. Opening sell-side…`)
      setTimeout(() => navigate('/inventory'), 800)
    },
    onError: (e) => setMsg(`❌ ${e?.response?.data?.detail || e.message}`),
  })

  const outreachMut = useMutation({
    mutationFn: sendListingOutreach,
    onSuccess: () => {
      setMsg('✉ Message queued — will send in background.')
      setTimeout(() => qc.invalidateQueries(['listings']), 3000)
    },
    onError: (e) => setMsg(`❌ ${e?.response?.data?.detail || e.message}`),
  })

  const pipelineMut = useMutation({
    mutationFn: runFullPipeline,
    onSuccess: (data) => {
      setMsg(`⚡ Pipeline started — pricing + listing running in background.`)
      setTimeout(() => navigate('/inventory'), 1200)
    },
    onError: (e) => setMsg(`❌ ${e?.response?.data?.detail || e.message}`),
  })

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Listings</div>
          <div className="page-subtitle">All scraped deals with scoring and alert status.</div>
        </div>
      </div>

      {msg && <div className={msg.startsWith('✅') ? 'success-box' : 'error-box'} style={{ marginBottom: 16 }}>{msg}</div>}

      <div className="card" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <div>
            <label>Source</label>
            <select value={filters.source} onChange={e => setFilters(f => ({ ...f, source: e.target.value }))}>
              <option value="">All</option>
              <option value="facebook">Facebook</option>
              <option value="auctionninja">AuctionNinja</option>
              <option value="mock">Mock</option>
            </select>
          </div>
          <div>
            <label>Watchlist</label>
            <select value={filters.watchlist_id} onChange={e => setFilters(f => ({ ...f, watchlist_id: e.target.value }))}>
              <option value="">All</option>
              {watchlists?.map(wl => <option key={wl.id} value={wl.id}>{wl.name}</option>)}
            </select>
          </div>
          <div>
            <label>Rating</label>
            <select value={filters.rating} onChange={e => setFilters(f => ({ ...f, rating: e.target.value }))}>
              <option value="">All</option>
              <option value="STEAL">STEAL</option>
              <option value="GREAT">GREAT</option>
              <option value="GOOD">GOOD</option>
              <option value="FAIR">FAIR</option>
              <option value="PASS">PASS</option>
            </select>
          </div>
          <div>
            <label>Show Ignored</label>
            <select value={String(filters.ignored)} onChange={e => setFilters(f => ({ ...f, ignored: e.target.value === 'true' }))}>
              <option value="false">Hide Ignored</option>
              <option value="true">Show Ignored Only</option>
            </select>
          </div>
        </div>
      </div>

      {rawModal && <RawModal id={rawModal} onClose={() => setRawModal(null)} />}
      {scoreModal && <ScoreModal listing={scoreModal} onClose={() => setScoreModal(null)} />}
      {claudeModal && <ClaudeModal listing={claudeModal} onClose={() => setClaudeModal(null)} />}

      {isLoading ? <div className="loading">Loading listings...</div> : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>📷</th>
                <th>Title</th>
                <th>Source</th>
                <th>Price</th>
                <th>Rating</th>
                <th>Net Flip</th>
                <th>Cons. Value</th>
                <th>Target Buy</th>
                <th>Claude</th>
                <th>Outreach</th>
                <th>Location</th>
                <th>First Seen</th>
                <th>Alert</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {listings?.map(l => (
                <tr key={l.id} style={{ opacity: l.ignored ? 0.45 : 1 }}>
                  <td style={{ padding: '6px 10px', width: 68 }}>
                    {l.image_url
                      ? <img src={l.image_url} alt="" className="listing-thumb" />
                      : <div className="listing-thumb-empty">No img</div>}
                  </td>
                  <td style={{ maxWidth: 280 }}>
                    <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {l.url
                        ? <a href={l.url} target="_blank" rel="noreferrer" style={{ color: 'var(--accent)', textDecoration: 'none' }}>
                            {l.title} <ExternalLink size={11} style={{ verticalAlign: 'middle' }} />
                          </a>
                        : l.title}
                    </div>
                    <SignalBadges listing={l} />
                  </td>
                  <td><span className="badge badge-blue">{l.source}</span></td>
                  <td>{l.price != null ? `$${l.price.toLocaleString()}` : '—'}</td>
                  <td><RatingBadge rating={l.deal_score?.rating} /></td>
                  <td onClick={() => l.deal_score && setScoreModal(l)} style={{ cursor: l.deal_score?.net_flip_score != null ? 'pointer' : 'default' }}>
                    <NetFlipBadge score={l.deal_score} />
                  </td>
                  <td>{fmtMoney(l.deal_score?.conservative_value)}</td>
                  <td>{fmtMoney(l.deal_score?.target_buy_price)}</td>
                  <td onClick={() => l.claude_review && setClaudeModal(l)} style={{ cursor: l.claude_review ? 'pointer' : 'default' }}>
                    <ClaudeReviewBadge
                      review={l.claude_review}
                      listingId={l.id}
                      onTrigger={(id) => claudeMut.mutate(id)}
                    />
                  </td>
                  <td>
                    {l.outreach_status === 'SENT' && (
                      <span className="badge badge-green" title={`Sent${l.outreach_sent_at ? ` ${fmtDate(l.outreach_sent_at)}` : ''}`}>✉ Sent</span>
                    )}
                    {l.outreach_status === 'QUEUED' && (
                      <span className="badge badge-blue">⏳ Queued</span>
                    )}
                    {l.outreach_status === 'FAILED' && (
                      <span className="badge badge-red">✗ Failed</span>
                    )}
                    {!l.outreach_status && (
                      <span className="text-muted" style={{ fontSize: 11 }}>—</span>
                    )}
                  </td>
                  <td className="text-muted" style={{ fontSize: 12 }}>{l.location || '—'}</td>
                  <td className="text-muted" style={{ fontSize: 12 }}>{fmtDate(l.first_seen_at)}</td>
                  <td>
                    {l.alert_sent
                      ? <span className="badge badge-green">Sent</span>
                      : <span className="badge badge-gray">—</span>}
                  </td>
                  <td>
                    <div className="actions-row">
                      <button className="btn btn-sm btn-secondary" title="View score" onClick={() => setScoreModal(l)}>
                        <Info size={12} />
                      </button>
                      <button className="btn btn-sm btn-secondary" title="Send to Discord" onClick={() => discordMut.mutate(l.id)}>
                        <Send size={12} />
                      </button>
                      {l.ignored
                        ? <button className="btn btn-sm btn-secondary" title="Unignore" onClick={() => unignoreMut.mutate(l.id)}><Eye size={12} /></button>
                        : <button className="btn btn-sm btn-secondary" title="Ignore" onClick={() => ignoreMut.mutate(l.id)}><EyeOff size={12} /></button>}
                      <button className="btn btn-sm btn-secondary" title="View raw" onClick={() => setRawModal(l.id)}>
                        {'{ }'}
                      </button>
                      {/* Only show outreach button for FB listings not yet messaged */}
                      {l.source === 'facebook' && l.outreach_status !== 'SENT' && (
                        <button
                          className="btn btn-sm btn-secondary"
                          title="Message seller on Facebook"
                          onClick={() => outreachMut.mutate(l.id)}
                          disabled={outreachMut.isPending || l.outreach_status === 'QUEUED'}
                          style={{ color: '#60a5fa', borderColor: 'rgba(96,165,250,0.4)' }}
                        >
                          <MessageCircle size={12} />
                        </button>
                      )}
                      <button
                        className="btn btn-sm btn-secondary"
                        title="Mark as purchased → add to sell-side inventory"
                        onClick={() => promoteMut.mutate(l.id)}
                        disabled={promoteMut.isPending}
                        style={{ color: 'var(--green)', borderColor: 'rgba(34,197,94,0.4)' }}
                      >
                        <Package size={12} />
                      </button>
                      {/* Full pipeline: promote + auto-price + auto-list */}
                      <button
                        className="btn btn-sm btn-secondary"
                        title="Full pipeline: add to inventory → auto-price → auto-list on Facebook"
                        onClick={() => pipelineMut.mutate(l.id)}
                        disabled={pipelineMut.isPending}
                        style={{ color: '#f59e0b', borderColor: 'rgba(245,158,11,0.4)' }}
                      >
                        <Zap size={12} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {!listings?.length && (
                <tr>
                  <td colSpan={14}>
                    <div className="empty-state">
                      <div className="icon">🔍</div>
                      <div>No listings yet. Run a scraper to start finding deals.</div>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
