import { useState, type FormEvent } from 'react'
import { ApiError, api } from '../api/client'
import type { Activity } from '../types'
import { Field, FormError, Modal, btn, inputCls } from './ui'

interface Props {
  draftId: string
  dayNumber: number
  activity?: Activity
  /** Pre-filled name (from a suggestion). */
  initialName?: string
  /** When set, the user picks the day (1..dayCount). */
  dayCount?: number
  onSaved: (message: string) => void
  onClose: () => void
}

/** Add or edit an activity (frontend-spec.md §7). */
export default function ActivityModal({ draftId, dayNumber, activity, initialName, dayCount, onSaved, onClose }: Props) {
  const [name, setName] = useState(activity?.destinationName ?? initialName ?? '')
  const [day, setDay] = useState(dayNumber)
  const [time, setTime] = useState(activity?.time ?? '')
  const [cost, setCost] = useState(activity?.cost?.toString() ?? '')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [formError, setFormError] = useState<string>()
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    const found: Record<string, string> = {}
    if (!name.trim()) found.destinationName = 'Enter a destination name.'
    const costNum = cost === '' ? null : Number(cost)
    if (costNum !== null && (Number.isNaN(costNum) || costNum < 0)) found.cost = 'Cost must be 0 or more.'
    setErrors(found)
    if (Object.keys(found).length) return
    const body = { destinationName: name.trim(), time: time || null, cost: costNum }
    setBusy(true)
    try {
      if (activity) await api(`/activities/${activity.id}`, 'PATCH', body)
      else await api(`/drafts/${draftId}/activities`, 'POST', { ...body, dayNumber: day })
      onSaved(activity ? 'Activity updated' : 'Activity added')
    } catch (err) {
      if (err instanceof ApiError && Object.keys(err.fields).length) setErrors(err.fields)
      else setFormError(err instanceof Error ? err.message : 'Something went wrong.')
      setBusy(false)
    }
  }

  const optional = <span className="font-normal text-slate-500">(optional)</span>
  return (
    <Modal title={`${activity ? 'Edit activity' : 'Add activity'} · Day ${day}`} onClose={onClose}>
      <form className="grid gap-4" onSubmit={submit} noValidate>
        <Field id="act-name" label="Destination name" error={errors.destinationName}>
          <input id="act-name" className={inputCls} maxLength={100} autoFocus placeholder="e.g. Baga Beach"
            value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field id="act-time" label={<>Start time {optional}</>} error={errors.time}>
            <input id="act-time" type="time" className={inputCls} value={time} onChange={(e) => setTime(e.target.value)} />
          </Field>
          <Field id="act-cost" label={<>Cost in ₹ {optional}</>} error={errors.cost}>
            <input id="act-cost" type="number" min="0" step="0.01" inputMode="decimal" className={inputCls}
              value={cost} onChange={(e) => setCost(e.target.value)} />
          </Field>
        </div>
        {dayCount && (
          <Field id="act-day" label="Day">
            <select id="act-day" className={inputCls} value={day} onChange={(e) => setDay(Number(e.target.value))}>
              {Array.from({ length: dayCount }, (_, i) => (
                <option key={i + 1} value={i + 1}>Day {i + 1}</option>
              ))}
            </select>
          </Field>
        )}
        <FormError message={formError} />
        <div className="flex justify-end gap-2">
          <button type="button" className={btn.ghost} onClick={onClose}>
            Cancel
          </button>
          <button className={btn.primary} disabled={busy}>
            {activity ? 'Save' : 'Add activity'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
