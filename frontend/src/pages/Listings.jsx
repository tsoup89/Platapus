import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { EyeOff, Eye, Send, ExternalLink, Info } from 'lucide-react'
import { getListings, ignoreListing, unignoreListing, sendDiscord, getListingRaw, getWatchlists } from '../api'

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

function ScoreModal({ listing, onClose }) {
  const score = listing.deal_score
  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={{ maxWidth: 500 }}>
        <div className="modal-header">
          <div className="modal-title">Deal Score — {listing.title.slice(0, 40)}</div>
          <button className="btn btn-secondary btn-sm" onClick={onClose}>✕</button>
        </div>
        {!score ? <div className="text-muted">No score available.</div> : (
          <>
            <div style={{ marginBottom: 16 }}>
              <RatingBadge rating={score.rating} />
              <span style={{ marginLeft: 8, fontSize: 18, fontWeight: 700 }}>{score.score?.toFixed(0)}/100</span>
            </div>
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
              <div>
                <div className="card-title">Warnings</div>
                <ul style={{ listStyle: 'none', padding: 0 }}>
                  {score.warnings.map((w, i) => <li key={i} style={{ fontSize: 13, marginBottom: 4, color: 'var(--yellow)' }}>⚠️ {w}</li>)}
                </ul>
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
  const [filters, setFilters] = useState({ source: '', watchlist_id: '', ignored: false })
  const [rawModal, setRawModal] = useState(null)
  const [scoreModal, setScoreModal] = useState(null)
  const [msg, setMsg] = useState(null)

  const { data: listings, isLoading } = useQuery({
    queryKey: ['listings', filters],
    queryFn: () => getListings({
      source: filters.source || undefined,
      watchlist_id: filters.watchlist_id || undefined,
      ignored: filters.ignored,
      limit: 100,
    }),
    refetchInterval: 30_000,
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

      {isLoading ? <div className="loading">Loading listings...</div> : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Title</th>
                <th>Source</th>
                <th>Price</th>
                <th>Rating</th>
                <th>Cons. Value</th>
                <th>Target Buy</th>
                <th>Location</th>
                <th>First Seen</th>
                <th>Alert</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {listings?.map(l => (
                <tr key={l.id} style={{ opacity: l.ignored ? 0.45 : 1 }}>
                  <td style={{ maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {l.url
                      ? <a href={l.url} target="_blank" rel="noreferrer" style={{ color: 'var(--accent)', textDecoration: 'none' }}>
                          {l.title} <ExternalLink size={11} style={{ verticalAlign: 'middle' }} />
                        </a>
                      : l.title}
                  </td>
                  <td><span className="badge badge-blue">{l.source}</span></td>
                  <td>{l.price != null ? `$${l.price.toLocaleString()}` : '—'}</td>
                  <td><RatingBadge rating={l.deal_score?.rating} /></td>
                  <td>{fmtMoney(l.deal_score?.conservative_value)}</td>
                  <td>{fmtMoney(l.deal_score?.target_buy_price)}</td>
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
                    </div>
                  </td>
                </tr>
              ))}
              {!listings?.length && (
                <tr>
                  <td colSpan={10}>
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
