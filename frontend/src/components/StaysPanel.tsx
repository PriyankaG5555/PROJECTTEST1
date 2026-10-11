import { useState, type FormEvent } from 'react'
import { ApiError, api } from '../api/client'
import type { Hotel, Stay, TripDetail } from '../types'
import { inr } from '../utils/format'
import { ConfirmDialog, Field, FormError, Modal, btn, card, inputCls } from './ui'

const KIND: Record<string, string> = {
  hotel: 'Hotel',
  guest_house: 'Guest house',
  hostel: 'Hostel',
  resort: 'Resort',
  apartment: 'Apartment',
  motel: 'Motel',
}

interface Draft {
  id?: string
  name: string
  checkInDay: number
  checkOutDay: number
  cost: string
  hotel?: Hotel
}

/** Stays by night range + OpenStreetMap hotel suggestions (accommodation-feature.md). */
export default function StaysPanel(props: { trip: TripDetail; readOnly: boolean; onChanged: (msg: string) => Promise<void> }) {
  const { trip, readOnly } = props
  const [form, setForm] = useState<Draft | null>(null)
  const [hotels, setHotels] = useState<Hotel[] | null>(null)
  const [attribution, setAttribution] = useState('')
  const [deleting, setDeleting] = useState<Stay | null>(null)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [error, setError] = useState<string>()
  const [busy, setBusy] = useState(false)
  const lastDay = trip.dayCount + 1
  const nextFree = () => {
    const taken = new Set(trip.stays.flatMap((s) => Array.from({ length: s.nights }, (_, i) => s.checkInDay + i)))
    const first = Array.from({ length: trip.dayCount }, (_, i) => i + 1).find((d) => !taken.has(d)) ?? 1
    return { checkInDay: first, checkOutDay: Math.min(first + 1, lastDay) }
  }

  async function findHotels() {
    setBusy(true)
    setError(undefined)
    try {
      const res = await api<{ hotels: Hotel[]; attribution: string }>(`/trips/${trip.id}/hotel-suggestions`)
      setHotels(res.hotels)
      setAttribution(res.attribution)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong.')
    } finally {
      setBusy(false)
    }
  }

  async function save(e: FormEvent) {
    e.preventDefault()
    if (!form) return
    const found: Record<string, string> = {}
    if (!form.name.trim()) found.name = 'Enter the place you stay at.'
    if (form.checkOutDay <= form.checkInDay) found.checkOutDay = 'Check-out must be after check-in.'
    const cost = form.cost === '' ? null : Number(form.cost)
    if (cost !== null && (Number.isNaN(cost) || cost < 0)) found.costPerNight = 'Cost must be 0 or more.'
    setErrors(found)
    if (Object.keys(found).length) return
    const h = form.hotel
    const body = {
      name: form.name.trim(),
      checkInDay: form.checkInDay,
      checkOutDay: form.checkOutDay,
      costPerNight: cost,
      ...(h && { placeId: h.placeId, kind: h.kind, stars: h.stars, lat: h.lat, lon: h.lon, address: h.address, url: h.mapsUrl }),
    }
    setBusy(true)
    try {
      if (form.id) await api(`/stays/${form.id}`, 'PATCH', body)
      else await api(`/trips/${trip.id}/stays`, 'POST', body)
      setForm(null)
      await props.onChanged(form.id ? 'Stay updated' : 'Stay added')
    } catch (err) {
      if (err instanceof ApiError && Object.keys(err.fields).length) setErrors(err.fields)
      else setError(err instanceof Error ? err.message : 'Something went wrong.')
    } finally {
      setBusy(false)
    }
  }

  const dayOptions = (from: number, to: number) =>
    Array.from({ length: to - from + 1 }, (_, i) => from + i).map((d) => (
      <option key={d} value={d}>
        Day {d}
      </option>
    ))

  return (
    <section className={`${card} grid gap-3 p-4`} aria-labelledby="stays-title">
      <div className="flex flex-wrap items-center gap-2">
        <h2 id="stays-title" className="flex-1 font-semibold">🏨 Stays</h2>
        {!readOnly && (
          <>
            <button className={btn.ghost} onClick={findHotels} disabled={busy}>
              {busy && !form ? 'Loading…' : hotels ? 'Refresh hotels' : 'Find hotels'}
            </button>
            <button className={btn.primary} onClick={() => { setErrors({}); setForm({ name: '', cost: '', ...nextFree() }) }}>
              + Add stay
            </button>
          </>
        )}
      </div>
      {error && <p className="text-sm text-red-700" role="alert">{error}</p>}
      {trip.stays.length === 0 ? (
        <p className="text-sm text-slate-600">No stays yet. Add where you sleep each night so Plan my day can start at your hotel.</p>
      ) : (
        <ul className="grid gap-2">
          {trip.stays.map((s) => (
            <li key={s.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-xl border border-brand-200 px-3 py-2">
              <span className="font-medium">{s.name}</span>
              <span className="text-sm text-slate-600">
                Day {s.checkInDay} → Day {s.checkOutDay} · {s.nights} night{s.nights > 1 ? 's' : ''}
                {s.costPerNight !== null && ` · ${inr(s.costPerNight)}/night`}
                {!s.verified && ' · location unknown'}
              </span>
              <span className="flex-1" />
              {s.totalCost !== null && <span className="tabular-nums">{inr(s.totalCost)}</span>}
              {!readOnly && (
                <span className="flex">
                  <button className={btn.text}
                    onClick={() => { setErrors({}); setForm({ id: s.id, name: s.name, checkInDay: s.checkInDay, checkOutDay: s.checkOutDay, cost: s.costPerNight?.toString() ?? '' }) }}>
                    Edit
                  </button>
                  <button className={`${btn.text} text-red-700`} onClick={() => setDeleting(s)} aria-label={`Delete stay ${s.name}`}>✕</button>
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
      {!!hotels && !readOnly && (
        <>
          {hotels.length === 0 ? (
            <p className="text-sm text-slate-600">No hotels found on the map for this destination.</p>
          ) : (
            <ul className="grid gap-2 sm:grid-cols-2">
              {hotels.map((h) => (
                <li key={h.placeId} className="flex items-start gap-3 rounded-xl border border-brand-200 p-3">
                  <span className="grid min-w-0 flex-1 gap-0.5">
                    <span className="font-medium break-words">{h.name}</span>
                    <span className="flex flex-wrap gap-x-3 text-sm text-slate-600">
                      <span>{KIND[h.kind] ?? h.kind}</span>
                      {h.stars && <span>{'★'.repeat(h.stars)}</span>}
                      {h.distanceKm !== null && <span>{h.distanceKm} km from sights</span>}
                      <a className="font-semibold text-brand-700" href={h.mapsUrl} target="_blank" rel="noreferrer">Map</a>
                      {h.website && <a className="font-semibold text-brand-700" href={h.website} target="_blank" rel="noreferrer">Website</a>}
                    </span>
                  </span>
                  <button className={btn.text} onClick={() => { setErrors({}); setForm({ name: h.name, cost: '', hotel: h, ...nextFree() }) }}>
                    Use this hotel
                  </button>
                </li>
              ))}
            </ul>
          )}
          <p className="text-xs text-slate-500">{attribution} · No prices or availability — book directly with the hotel.</p>
        </>
      )}

      {form && (
        <Modal title={form.id ? 'Edit stay' : 'Add stay'} onClose={() => setForm(null)}>
          <form className="grid gap-4" onSubmit={save} noValidate>
            <Field id="stay-name" label="Where you stay" error={errors.name}>
              <input id="stay-name" className={inputCls} maxLength={100} autoFocus value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value, hotel: undefined })} />
            </Field>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field id="stay-in" label="Check-in" error={errors.checkInDay}>
                <select id="stay-in" className={inputCls} value={form.checkInDay}
                  onChange={(e) => setForm({ ...form, checkInDay: Number(e.target.value) })}>
                  {dayOptions(1, trip.dayCount)}
                </select>
              </Field>
              <Field id="stay-out" label="Check-out" error={errors.checkOutDay}>
                <select id="stay-out" className={inputCls} value={form.checkOutDay}
                  onChange={(e) => setForm({ ...form, checkOutDay: Number(e.target.value) })}>
                  {dayOptions(2, lastDay)}
                </select>
              </Field>
            </div>
            <Field id="stay-cost" label={<>Cost per night in ₹ <span className="font-normal text-slate-500">(optional)</span></>} error={errors.costPerNight}>
              <input id="stay-cost" type="number" min="0" step="1" inputMode="numeric" className={inputCls}
                value={form.cost} onChange={(e) => setForm({ ...form, cost: e.target.value })} />
            </Field>
            {form.hotel && <p className="text-sm text-slate-600">📍 Location from OpenStreetMap — Plan my day will start here.</p>}
            <FormError message={error} />
            <div className="flex justify-end gap-2">
              <button type="button" className={btn.ghost} onClick={() => setForm(null)}>Cancel</button>
              <button className={btn.primary} disabled={busy}>{form.id ? 'Save' : 'Add stay'}</button>
            </div>
          </form>
        </Modal>
      )}
      {deleting && (
        <ConfirmDialog title="Delete this stay?" danger busy={busy} confirmLabel="Delete stay"
          message={`“${deleting.name}” will be removed from your trip.`}
          onClose={() => setDeleting(null)}
          onConfirm={async () => {
            setBusy(true)
            try {
              await api(`/stays/${deleting.id}`, 'DELETE')
              setDeleting(null)
              await props.onChanged('Stay deleted')
            } catch (err) {
              setError(err instanceof Error ? err.message : 'Something went wrong.')
            } finally {
              setBusy(false)
            }
          }} />
      )}
    </section>
  )
}
