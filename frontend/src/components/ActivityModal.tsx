import { useState, type FormEvent } from 'react'
import { ApiError, api } from '../api/client'
import { PRIORITIES, type Activity, type Priority } from '../types'
import { Field, FormError, Modal, btn, inputCls } from './ui'

interface Props {
  draftId: string
  dayNumber: number
  activity?: Activity
  onSaved: (message: string) => void
  onClose: () => void
}

/** Add or edit an activity (frontend-spec.md §7). */
export default function ActivityModal({ draftId, dayNumber, activity, onSaved, onClose }: Props) {
  const [name, setName] = useState(activity?.destinationName ?? '')
  const [time, setTime] = useState(activity?.time ?? '')
  const [cost, setCost] = useState(activity?.cost?.toString() ?? '')
  const [priority, setPriority] = useState<Priority | ''>(activity?.priority ?? '')
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
    const body = { destinationName: name.trim(), time: time || null, cost: costNum, priority: priority || null }
    setBusy(true)
    try {
      if (activity) await api(`/activities/${activity.id}`, 'PATCH', body)
      else await api(`/drafts/${draftId}/activities`, 'POST', { ...body, dayNumber })
      onSaved(activity ? 'Activity updated' : 'Activity added')
    } catch (err) {
      if (err instanceof ApiError && Object.keys(err.fields).length) setErrors(err.fields)
      else setFormError(err instanceof Error ? err.message : 'Something went wrong.')
      setBusy(false)
    }
  }

  const optional = <span className="font-normal text-slate-500">(optional)</span>
  return (
    <Modal title={`${activity ? 'Edit activity' : 'Add activity'} · Day ${dayNumber}`} onClose={onClose}>
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
        <fieldset className="grid gap-1.5">
          <legend className="mb-1 text-sm font-medium">Priority {optional}</legend>
          <div className="flex flex-wrap gap-2">
            {([['', 'None'], ...Object.entries(PRIORITIES)] as [Priority | '', string][]).map(([k, label]) => (
              <label key={k || 'none'}
                className="flex cursor-pointer items-center gap-1.5 rounded-lg border border-brand-400 px-2.5 py-1.5 text-sm has-checked:bg-brand-50">
                <input type="radio" name="priority" checked={priority === k} onChange={() => setPriority(k)} />
                {label}
              </label>
            ))}
          </div>
        </fieldset>
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
