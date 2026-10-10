import { useState, type FormEvent } from 'react'
import { ApiError, api } from '../api/client'
import type { AIPlan, Activity } from '../types'
import { durationLabel, endTime } from '../utils/format'
import { Field, FormError, Modal, btn, inputCls } from './ui'

interface Props {
  tripId: string
  draftId: string
  dayNumber: number
  dateLabel: string
  onApplied: (message: string) => Promise<void>
  onClose: () => void
}

const list = (text: string) =>
  text
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)

/** "Plan this day with AI" — request, review, apply selected (specs/ai-feature.md §3). */
export default function AIPlanModal({ tripId, draftId, dayNumber, dateLabel, onApplied, onClose }: Props) {
  const [start, setStart] = useState('09:00')
  const [end, setEnd] = useState('18:00')
  const [interests, setInterests] = useState('')
  const [mustVisit, setMustVisit] = useState('')
  const [avoid, setAvoid] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [error, setError] = useState<string>()
  const [busy, setBusy] = useState(false)
  const [plan, setPlan] = useState<AIPlan | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())

  async function generate(e?: FormEvent) {
    e?.preventDefault()
    const found: Record<string, string> = {}
    if (!start) found.startTime = 'Choose a start time.'
    if (!end) found.endTime = 'Choose an end time.'
    else if (start && end <= start) found.endTime = 'End time must be after the start time.'
    if (list(interests).length > 5) found.interests = 'Use at most 5 interests.'
    setErrors(found)
    setError(undefined)
    if (Object.keys(found).length) return
    setBusy(true)
    try {
      const result = await api<AIPlan>(`/trips/${tripId}/ai-plans`, 'POST', {
        draftId,
        dayNumber,
        startTime: start,
        endTime: end,
        interests: list(interests),
        mustVisit: list(mustVisit),
        avoid: list(avoid),
      })
      setPlan(result)
      setSelected(new Set(result.activities.map((a) => a.itemId)))
    } catch (err) {
      if (err instanceof ApiError && Object.keys(err.fields).length) setErrors(err.fields)
      else setError(err instanceof Error ? err.message : 'Something went wrong.')
    } finally {
      setBusy(false)
    }
  }

  async function applySelected() {
    if (!plan) return
    setBusy(true)
    setError(undefined)
    try {
      const res = await api<{ activities: Activity[] }>(`/drafts/${draftId}/activities/bulk`, 'POST', {
        proposalToken: plan.proposalToken,
        selectedItemIds: [...selected],
      })
      await onApplied(`${res.activities.length} AI suggestion${res.activities.length === 1 ? '' : 's'} added`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong.')
      setBusy(false)
    }
  }

  const toggle = (id: string) =>
    setSelected((s) => {
      const next = new Set(s)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  return (
    <Modal title={`Plan Day ${dayNumber} with AI · ${dateLabel}`} onClose={onClose} wide>
      {!plan ? (
        <form className="grid gap-4" onSubmit={generate} noValidate>
          <p className="text-sm text-slate-600">
            Tell us when you're free. Your existing activities for this day stay as they are, and nothing is saved
            until you choose what to add.
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field id="ai-start" label="From" error={errors.startTime}>
              <input id="ai-start" type="time" className={inputCls} value={start} onChange={(e) => setStart(e.target.value)} />
            </Field>
            <Field id="ai-end" label="Until" error={errors.endTime}>
              <input id="ai-end" type="time" className={inputCls} value={end} onChange={(e) => setEnd(e.target.value)} />
            </Field>
          </div>
          <Field id="ai-interests" label="Interests (optional)" error={errors.interests} hint="Comma-separated, e.g. museums, local food">
            <input id="ai-interests" className={inputCls} value={interests} onChange={(e) => setInterests(e.target.value)} />
          </Field>
          <Field id="ai-must" label="Must visit (optional)" error={errors.mustVisit} hint="Comma-separated place names">
            <input id="ai-must" className={inputCls} value={mustVisit} onChange={(e) => setMustVisit(e.target.value)} />
          </Field>
          <Field id="ai-avoid" label="Places to avoid (optional)" error={errors.avoid}>
            <input id="ai-avoid" className={inputCls} value={avoid} onChange={(e) => setAvoid(e.target.value)} />
          </Field>
          <FormError message={error} />
          <div className="flex justify-end gap-2">
            <button type="button" className={btn.ghost} onClick={onClose}>
              Cancel
            </button>
            <button className={btn.primary} disabled={busy}>
              {busy ? 'Planning…' : 'Suggest a plan'}
            </button>
          </div>
        </form>
      ) : (
        <div className="grid gap-4">
          <p className="rounded-xl bg-brand-50 px-3 py-2 text-sm">
            AI-assisted suggestions for {start}–{end}. Durations are estimates — check opening hours and prices with
            each place.
          </p>
          {plan.activities.length === 0 ? (
            <p className="text-slate-600">No suggestions fit this time window.</p>
          ) : (
            <ul className="grid gap-2">
              {plan.activities.map((a) => (
                <li key={a.itemId}>
                  <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-brand-200 p-3 has-checked:border-brand-400 has-checked:bg-brand-50">
                    <input type="checkbox" className="mt-1" checked={selected.has(a.itemId)} onChange={() => toggle(a.itemId)} />
                    <span className="grid min-w-0 flex-1 gap-0.5">
                      <span className="flex flex-wrap items-center gap-2">
                        <b className="tabular-nums">
                          {a.time}–{endTime(a.time, a.durationMinutes)}
                        </b>
                        <span className="font-medium break-words">{a.destinationName}</span>
                        {!a.verified && (
                          <span className="rounded-md bg-amber-100 px-1.5 text-xs font-bold text-amber-800">Unverified place</span>
                        )}
                      </span>
                      <span className="text-sm text-slate-600">
                        {durationLabel(a.durationMinutes)} (AI estimate) · {a.source}
                        {a.mapsUrl && (
                          <>
                            {' · '}
                            <a className="font-semibold text-brand-700" href={a.mapsUrl} target="_blank" rel="noreferrer">
                              Map
                            </a>
                          </>
                        )}
                      </span>
                      {a.reason && <span className="text-sm text-slate-600 italic">AI note: {a.reason}</span>}
                    </span>
                  </label>
                </li>
              ))}
            </ul>
          )}
          {plan.warnings.length > 0 && (
            <ul className="grid list-disc gap-1 rounded-xl bg-amber-50 py-2 pr-3 pl-7 text-sm text-amber-900">
              {plan.warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          )}
          {plan.activities.some((a) => a.attribution) && <p className="text-xs text-slate-500">Powered by Google</p>}
          <FormError message={error} />
          <div className="flex flex-wrap justify-end gap-2">
            <button className={btn.ghost} onClick={() => setPlan(null)} disabled={busy}>
              Change details
            </button>
            <button className={btn.ghost} onClick={() => generate()} disabled={busy}>
              Generate again
            </button>
            <button className={btn.primary} onClick={applySelected} disabled={busy || selected.size === 0}>
              Add selected to plan ({selected.size})
            </button>
          </div>
        </div>
      )}
    </Modal>
  )
}
