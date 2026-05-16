import { useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Upload, Search, Star, RefreshCw } from 'lucide-react'
import { getGCPrices, updateGCPrice, importGCCSV, getUnmatched, rescoreGamecube } from '../api'

function fmtMoney(v) {
  if (v == null) return '—'
  return `$${Number(v).toFixed(2)}`
}

function EditablePrice({ priceId, field, value }) {
  const qc = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [val, setVal] = useState(value)

  const mut = useMutation({
    mutationFn: (v) => updateGCPrice(priceId, { [field]: v ? parseFloat(v) : null }),
    onSuccess: () => { qc.invalidateQueries(['gc-prices']); setEditing(false) },
  })

  if (!editing) {
    return (
      <span
        onClick={() => setEditing(true)}
        style={{ cursor: 'pointer', borderBottom: '1px dashed var(--border)' }}
        title="Click to edit"
      >
        {fmtMoney(value)}
      </span>
    )
  }

  return (
    <input
      type="number"
      style={{ width: 70, fontSize: 12 }}
      value={val || ''}
      onChange={e => setVal(e.target.value)}
      onBlur={() => mut.mutate(val)}
      onKeyDown={e => { if (e.key === 'Enter') mut.mutate(val); if (e.key === 'Escape') setEditing(false) }}
      autoFocus
    />
  )
}

export default function PricingTables() {
  const qc = useQueryClient()
  const fileRef = useRef()
  const [search, setSearch] = useState('')
  const [msg, setMsg] = useState(null)

  const { data: prices, isLoading } = useQuery({
    queryKey: ['gc-prices', search],
    queryFn: () => getGCPrices({ search, limit: 200 }),
  })

  const { data: unmatched } = useQuery({
    queryKey: ['gc-unmatched'],
    queryFn: getUnmatched,
  })

  const importMut = useMutation({
    mutationFn: importGCCSV,
    onSuccess: (data) => {
      setMsg(`✅ ${data.message}`)
      qc.invalidateQueries(['gc-prices'])
      qc.invalidateQueries(['listings'])
    },
    onError: (e) => setMsg(`❌ ${e?.response?.data?.detail || e.message}`),
  })

  const rescoreMut = useMutation({
    mutationFn: rescoreGamecube,
    onSuccess: (data) => {
      setMsg(`✅ ${data.message}`)
      qc.invalidateQueries(['listings'])
    },
    onError: (e) => setMsg(`❌ ${e?.response?.data?.detail || e.message}`),
  })

  const handleFileChange = (e) => {
    const file = e.target.files[0]
    if (file) importMut.mutate(file)
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Pricing Tables</div>
          <div className="page-subtitle">GameCube game prices for bundle valuation and deal scoring.</div>
        </div>
        <div className="actions-row">
          <input ref={fileRef} type="file" accept=".csv" style={{ display: 'none' }} onChange={handleFileChange} />
          <button
            className="btn btn-secondary"
            onClick={() => rescoreMut.mutate()}
            disabled={rescoreMut.isPending}
            title="Re-score all GameCube listings using current prices"
          >
            <RefreshCw size={14} />
            {rescoreMut.isPending ? 'Rescoring...' : 'Re-score Listings'}
          </button>
          <button
            className="btn btn-primary"
            onClick={() => fileRef.current.click()}
            disabled={importMut.isPending}
          >
            <Upload size={14} />
            {importMut.isPending ? 'Importing...' : 'Import CSV'}
          </button>
        </div>
      </div>

      {msg && (
        <div className={msg.startsWith('✅') ? 'success-box' : 'error-box'} style={{ marginBottom: 16 }}>
          {msg}
        </div>
      )}

      <div className="card" style={{ marginBottom: 12 }}>
        <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 8 }}>
          CSV format: <code style={{ background: 'var(--bg)', padding: '1px 6px', borderRadius: 4 }}>Game, Loose Price, Complete Price, New Price, Graded Price, Box Only, Manual Only</code>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Search size={14} color="var(--text-muted)" />
          <input
            type="text"
            placeholder="Search game titles..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{ flex: 1 }}
          />
        </div>
      </div>

      {unmatched?.length > 0 && (
        <div className="card" style={{ marginBottom: 16, borderColor: 'rgba(245,158,11,0.4)' }}>
          <div className="card-title" style={{ color: 'var(--yellow)' }}>
            ⚠️ {unmatched.length} Unmatched Title(s) — Manual Review Needed
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>
            These listing fragments could not be matched to a known game. Improve your pricing CSV or add aliases.
          </div>
          <div className="tag-list">
            {unmatched.map(m => (
              <span key={m.id} className="tag" title={`Confidence: ${(m.confidence * 100).toFixed(0)}%`}>
                {m.raw_text}
              </span>
            ))}
          </div>
        </div>
      )}

      {isLoading ? <div className="loading">Loading prices...</div> : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Game Title</th>
                <th>Core</th>
                <th>Demand</th>
                <th>Loose</th>
                <th>Complete</th>
                <th>New</th>
                <th>Graded</th>
                <th>Updated</th>
              </tr>
            </thead>
            <tbody>
              {prices?.map(p => (
                <tr key={p.id}>
                  <td>
                    <div style={{ fontWeight: p.core_title ? 600 : 400 }}>{p.title}</div>
                    {p.aliases?.length > 0 && (
                      <div className="text-muted" style={{ fontSize: 11 }}>
                        aliases: {p.aliases.join(', ')}
                      </div>
                    )}
                  </td>
                  <td>{p.core_title && <Star size={14} color="var(--yellow)" fill="var(--yellow)" />}</td>
                  <td>
                    <span className={`badge ${p.demand_tier === 'high' ? 'badge-orange' : p.demand_tier === 'low' ? 'badge-gray' : 'badge-blue'}`}>
                      {p.demand_tier}
                    </span>
                  </td>
                  <td><EditablePrice priceId={p.id} field="loose_price" value={p.loose_price} /></td>
                  <td><EditablePrice priceId={p.id} field="complete_price" value={p.complete_price} /></td>
                  <td><EditablePrice priceId={p.id} field="new_price" value={p.new_price} /></td>
                  <td><EditablePrice priceId={p.id} field="graded_price" value={p.graded_price} /></td>
                  <td className="text-muted" style={{ fontSize: 12 }}>
                    {p.last_updated ? new Date(p.last_updated + 'Z').toLocaleDateString() : '—'}
                  </td>
                </tr>
              ))}
              {!prices?.length && (
                <tr>
                  <td colSpan={8}>
                    <div className="empty-state">
                      <div className="icon">🎮</div>
                      <div>No GameCube prices loaded yet. Import a CSV to get started.</div>
                      <div className="text-muted" style={{ marginTop: 8, fontSize: 12 }}>
                        Download pricing from PriceCharting.com or use the sample CSV.
                      </div>
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
