import { useState, type FormEvent } from 'react'
import { ApiError, api } from '../api/client'
import type { Draft, TripDetail } from '../types'
import { ConfirmDialog, Field, FormError, Modal, btn, inputCls } from './ui'

interface Props {
  trip: TripDetail
  selectedId: string
  onSelect: (draftId: string) => void
  onChanged: (message: string, selectId?: string) => Promise<void>
}

type Dialog = 'new' | 'rename' | 'delete' | null

/** Switch, create (blank/copy), rename and delete drafts (frontend-spec.md Flow 3). */
export default function DraftSwitcher({ trip, selectedId, onSelect, onChanged }: Props) {
  const [dialog, setDialog] = useState<Dialog>(null)
  const [name, setName] = useState('')
  const [copyFrom, setCopyFrom] = useState('')
  const [error, setError] = useState<string>()
  const [busy, setBusy] = useState(false)
  const readOnly = trip.status === 'finalized'
  const selected = trip.drafts.find((d) => d.id === selectedId)

  function open(kind: Dialog) {
    setError(undefined)
    setName(kind === 'rename' ? (selected?.name ?? '') : `Draft ${trip.drafts.length + 1}`)
    setCopyFrom(selectedId)
    setDialog(kind)
  }

  async function run(action: () => Promise<{ message: string; selectId?: string }>) {
    setBusy(true)
    try {
      const { message, selectId } = await action()
      setDialog(null)
      await onChanged(message, selectId)
    } catch (err) {
      setError(err instanceof ApiError ? (Object.values(err.fields)[0] ?? err.message) : 'Something went wrong.')
    } finally {
      setBusy(false)
    }
  }

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return setError('Enter a draft name.')
    void run(async () => {
      if (dialog === 'rename') {
        await api(`/drafts/${selectedId}`, 'PATCH', { name: name.trim() })
        return { message: 'Draft renamed' }
      }
      const { draft } = await api<{ draft: Draft }>(`/trips/${trip.id}/drafts`, 'POST', {
        name: name.trim(),
        copyFromDraftId: copyFrom || null,
      })
      return { message: copyFrom ? 'Draft copied' : 'Blank draft created', selectId: draft.id }
    })
  }

  return (
    <div className="flex flex-wrap items-center gap-2 border-t border-brand-200 pt-3">
      <span className="mr-1 text-xs font-semibold tracking-wider text-slate-600 uppercase">Drafts</span>
      {trip.drafts.map((d) => (
        <button key={d.id} onClick={() => onSelect(d.id)} aria-pressed={d.id === selectedId}
          className="inline-flex items-center gap-1.5 rounded-full border border-brand-400 px-3 py-1 text-sm font-medium aria-pressed:border-brand-700 aria-pressed:bg-brand-700 aria-pressed:text-white">
          {d.name}
          {d.isFinal && <span className="rounded-full bg-green-100 px-1.5 text-[0.68rem] font-bold text-green-800">Final</span>}
        </button>
      ))}
      {!readOnly && (
        <>
          <button className={btn.text} onClick={() => (trip.drafts.length >= 5 ? setError('A trip can have up to 5 drafts. Delete one first.') : open('new'))}>
            + New draft
          </button>
          <button className={btn.text} onClick={() => open('rename')}>Rename</button>
          <button className={btn.text} disabled={trip.drafts.length < 2} onClick={() => open('delete')}>Delete</button>
        </>
      )}
      {error && !dialog && <span className="text-sm text-red-700" role="alert">{error}</span>}

      {(dialog === 'new' || dialog === 'rename') && (
        <Modal title={dialog === 'new' ? 'New draft' : 'Rename draft'} onClose={() => setDialog(null)}>
          <form className="grid gap-4" onSubmit={submit} noValidate>
            <Field id="draft-name" label="Draft name">
              <input id="draft-name" className={inputCls} maxLength={50} autoFocus value={name}
                onChange={(e) => setName(e.target.value)} />
            </Field>
            {dialog === 'new' && (
              <Field id="draft-from" label="Start from">
                <select id="draft-from" className={inputCls} value={copyFrom} onChange={(e) => setCopyFrom(e.target.value)}>
                  <option value="">Blank plan</option>
                  {trip.drafts.map((d) => (
                    <option key={d.id} value={d.id}>Copy of {d.name}</option>
                  ))}
                </select>
              </Field>
            )}
            <FormError message={error} />
            <div className="flex justify-end gap-2">
              <button type="button" className={btn.ghost} onClick={() => setDialog(null)}>Cancel</button>
              <button className={btn.primary} disabled={busy}>{dialog === 'new' ? 'Create draft' : 'Save'}</button>
            </div>
          </form>
        </Modal>
      )}
      {dialog === 'delete' && selected && (
        <ConfirmDialog title="Delete this draft?" danger busy={busy} error={error} confirmLabel="Delete draft"
          message={`“${selected.name}” and its activities will be deleted.`}
          onClose={() => setDialog(null)}
          onConfirm={() =>
            run(async () => {
              await api(`/drafts/${selectedId}`, 'DELETE')
              return { message: 'Draft deleted', selectId: trip.drafts.find((d) => d.id !== selectedId)?.id }
            })
          }
        />
      )}
    </div>
  )
}
