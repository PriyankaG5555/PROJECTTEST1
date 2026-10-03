import { useState } from 'react'
import { ApiError, api } from '../api/client'
import { TOP_PRIORITIES, type Suggestion, type TopPriority, type TripDetail } from '../types'
import { btn, card } from './ui'

const PRICE: Record<string, string> = {
  free: 'Free',
  inexpensive: '₹ Inexpensive',
  moderate: '₹₹ Moderate',
  expensive: '₹₹₹ Expensive',
  very_expensive: '₹₹₹₹ Very expensive',
}

const ORDER_NOTE: Record<TopPriority, string> = {
  budget: 'cheapest first',
  destinations: 'must-see first',
  time: 'best-rated first',
}

/** Google Places suggestions for the trip destination (goal-spec F11, contract §5). */
export default function SuggestionsPanel(props: { trip: TripDetail; readOnly: boolean; onAdd: (name: string) => void }) {
  const { trip } = props
  const [items, setItems] = useState<Suggestion[] | null>(null)
  const [error, setError] = useState<string>()
  const [busy, setBusy] = useState(false)

  async function load() {
    setBusy(true)
    setError(undefined)
    try {
      const res = await api<{ suggestions: Suggestion[] }>(`/trips/${trip.id}/suggestions`)
      setItems(res.suggestions)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className={`${card} grid gap-3 p-4`} aria-labelledby="suggestions-title">
      <div className="flex flex-wrap items-center gap-3">
        <h2 id="suggestions-title" className="flex-1 font-semibold">
          Places to visit in {trip.destination}
          {trip.topPriority && (
            <span className="ml-2 text-sm font-normal text-slate-600">
              ({TOP_PRIORITIES[trip.topPriority]} priority: {ORDER_NOTE[trip.topPriority]})
            </span>
          )}
        </h2>
        <button className={btn.ghost} onClick={load} disabled={busy}>
          {busy ? 'Loading…' : items ? 'Refresh' : 'Get suggestions'}
        </button>
      </div>
      {error && <p className="text-sm text-red-700" role="alert">{error}</p>}
      {items?.length === 0 && <p className="text-sm text-slate-600">No suggestions found for this destination.</p>}
      {!!items?.length && (
        <>
          <ul className="grid gap-2 sm:grid-cols-2">
            {items.map((s) => (
              <li key={s.placeId} className="flex items-start gap-3 rounded-xl border border-brand-200 p-3">
                <div className="grid min-w-0 flex-1 gap-0.5">
                  <span className="font-medium break-words">{s.name}</span>
                  <span className="flex flex-wrap gap-x-3 text-sm text-slate-600">
                    {s.rating !== null && (
                      <span>
                        ★ {s.rating.toFixed(1)}
                        {s.ratingCount !== null && ` (${s.ratingCount.toLocaleString('en-IN')})`}
                      </span>
                    )}
                    {s.priceLevel && <span>{PRICE[s.priceLevel] ?? s.priceLevel}</span>}
                    {s.mapsUrl && (
                      <a className="font-semibold text-brand-700" href={s.mapsUrl} target="_blank" rel="noreferrer">
                        Map
                      </a>
                    )}
                  </span>
                </div>
                {!props.readOnly && (
                  <button className={btn.text} onClick={() => props.onAdd(s.name)}>
                    + Add to plan
                  </button>
                )}
              </li>
            ))}
          </ul>
          <p className="text-xs text-slate-500">Powered by Google</p>
        </>
      )}
    </section>
  )
}
