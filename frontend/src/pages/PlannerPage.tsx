import { useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'
import { api, exportPdfUrl } from '../api/client'
import { useDraft, useRefreshData, useTrip } from '../api/queries'
import ActivityModal from '../components/ActivityModal'
import DraftSwitcher from '../components/DraftSwitcher'
import { useToast } from '../components/toast'
import { ConfirmDialog, ErrorState, PriorityLabel, Spinner, StatusBadge, btn, card } from '../components/ui'
import { TRIP_TYPES, type Activity, type Day } from '../types'
import { inr, longDate } from '../utils/format'

type Confirm = { kind: 'finalize' | 'reopen' } | { kind: 'delete-activity'; activity: Activity } | null

export default function PlannerPage() {
  const { tripId = '' } = useParams()
  const [params, setParams] = useSearchParams()
  const trip = useTrip(tripId)
  const draftId = params.get('draft') ?? trip.data?.finalizedDraftId ?? trip.data?.drafts[0]?.id
  const draft = useDraft(draftId)
  const refresh = useRefreshData()
  const toast = useToast()
  const [editing, setEditing] = useState<{ day: number; activity?: Activity } | null>(null)
  const [confirm, setConfirm] = useState<Confirm>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string>()

  if (trip.isPending) return <Spinner />
  if (trip.isError) return <ErrorState message={trip.error.message} onRetry={() => trip.refetch()} />
  const t = trip.data
  const readOnly = t.status === 'finalized'
  const finalName = t.drafts.find((d) => d.isFinal)?.name

  const select = (id: string) => setParams({ draft: id }, { replace: true })
  async function changed(message: string, selectId?: string) {
    await refresh()
    if (selectId) select(selectId)
    toast(message)
  }
  async function act(path: string, method: 'POST' | 'DELETE', message: string) {
    setBusy(true)
    setError(undefined)
    try {
      await api(path, method, path.endsWith('/finalize') ? { draftId } : undefined)
      setConfirm(null)
      await changed(message)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <div>
        <Link to="/trips" className={btn.text}>← My trips</Link>
      </div>
      <section className={`${card} grid gap-4 p-5`} aria-labelledby="trip-title">
        <div className="flex flex-wrap items-end gap-3">
          <div className="grid min-w-0 flex-1 gap-1">
            <div className="flex flex-wrap items-center gap-2.5">
              <h1 id="trip-title" className="text-2xl font-bold">{t.destination}</h1>
              <StatusBadge status={t.status} />
            </div>
            <p className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-slate-600">
              <span>{longDate(t.startDate)} – {longDate(t.endDate)}</span>
              <span>{t.dayCount} days</span>
              <span>{TRIP_TYPES[t.tripType]}</span>
              {draft.data && <span>Total <b className="tabular-nums">{inr(draft.data.totalCost)}</b></span>}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {readOnly ? (
              <>
                <a href={exportPdfUrl(t.id)} className={btn.primary}>Export PDF</a>
                <button className={btn.ghost} onClick={() => setConfirm({ kind: 'reopen' })}>Reopen for editing</button>
              </>
            ) : (
              <>
                <button className={btn.primary} onClick={() => setConfirm({ kind: 'finalize' })}>Finalize this draft</button>
                <Link to={`/trips/${t.id}/edit`} className={btn.ghost}>Edit trip</Link>
              </>
            )}
            {t.drafts.length > 1 && (
              <Link to={`/trips/${t.id}/compare?a=${draftId}`} className={btn.ghost}>Compare drafts</Link>
            )}
          </div>
        </div>
        {readOnly && (
          <p className="rounded-xl bg-green-50 px-3 py-2 text-sm font-medium text-green-800">
            🔒 Finalized from “{finalName}”. All drafts are read-only. Reopen to make changes.
          </p>
        )}
        {draftId && <DraftSwitcher trip={t} selectedId={draftId} onSelect={select} onChanged={changed} />}
      </section>

      {draft.isPending && <Spinner />}
      {draft.isError && <ErrorState message={draft.error.message} onRetry={() => draft.refetch()} />}
      {draft.data && (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(270px,1fr))] items-start gap-4">
          {draft.data.days.map((day) => (
            <DayCard key={day.dayNumber} day={day} readOnly={readOnly}
              onAdd={() => setEditing({ day: day.dayNumber })}
              onEdit={(a) => setEditing({ day: day.dayNumber, activity: a })}
              onDelete={(a) => setConfirm({ kind: 'delete-activity', activity: a })} />
          ))}
        </div>
      )}

      {editing && draftId && (
        <ActivityModal draftId={draftId} dayNumber={editing.day} activity={editing.activity}
          onClose={() => setEditing(null)}
          onSaved={async (msg) => { setEditing(null); await changed(msg) }} />
      )}
      {confirm?.kind === 'finalize' && (
        <ConfirmDialog title="Finalize this trip?" confirmLabel="Finalize" busy={busy} error={error}
          message={`“${t.drafts.find((d) => d.id === draftId)?.name}” becomes the final plan. The trip and all its drafts become read-only, and you can export the itinerary as a PDF.`}
          onClose={() => setConfirm(null)}
          onConfirm={() => act(`/trips/${t.id}/finalize`, 'POST', 'Trip finalized. You can now export the PDF.')} />
      )}
      {confirm?.kind === 'reopen' && (
        <ConfirmDialog title="Reopen for editing?" confirmLabel="Reopen" busy={busy} error={error}
          message="The trip goes back to Draft so you can change it. Export is unavailable until you finalize it again."
          onClose={() => setConfirm(null)}
          onConfirm={() => act(`/trips/${t.id}/reopen`, 'POST', 'Trip reopened as a draft')} />
      )}
      {confirm?.kind === 'delete-activity' && (
        <ConfirmDialog title="Delete activity?" confirmLabel="Delete" danger busy={busy} error={error}
          message={`“${confirm.activity.destinationName}” will be removed from Day ${confirm.activity.dayNumber}.`}
          onClose={() => setConfirm(null)}
          onConfirm={() => act(`/activities/${confirm.activity.id}`, 'DELETE', 'Activity deleted')} />
      )}
    </>
  )
}

function DayCard(props: {
  day: Day
  readOnly: boolean
  onAdd: () => void
  onEdit: (a: Activity) => void
  onDelete: (a: Activity) => void
}) {
  const { day, readOnly } = props
  return (
    <section className={`${card} grid min-w-0`} aria-label={`Day ${day.dayNumber}`}>
      <header className="flex items-baseline justify-between gap-2 rounded-t-2xl border-b border-brand-200 bg-brand-50 px-4 py-3">
        <span className="font-display font-bold">Day {day.dayNumber}</span>
        <span className="text-sm text-slate-600">{longDate(day.date)}</span>
      </header>
      {day.activities.length === 0 ? (
        <p className="px-4 py-3 text-sm text-slate-600">No activities yet{readOnly ? '' : ' — add one'}.</p>
      ) : (
        <ul className="grid divide-y divide-brand-200 px-2 py-1">
          {day.activities.map((a) => (
            <li key={a.id} className="grid grid-cols-[3.25rem_1fr_auto] items-start gap-2 px-2 py-2">
              <span className={`text-sm tabular-nums ${a.time ? 'font-semibold text-brand-700' : 'text-slate-500'}`}>
                {a.time ?? '—'}
              </span>
              <span className="grid min-w-0 gap-0.5">
                <span className="font-medium break-words">{a.destinationName}</span>
                <span className="flex flex-wrap items-center gap-2 text-sm text-slate-600">
                  {a.cost !== null && <span className="tabular-nums">{inr(a.cost)}</span>}
                  <PriorityLabel priority={a.priority} />
                </span>
              </span>
              {!readOnly && (
                <span className="flex">
                  <button className={btn.text} onClick={() => props.onEdit(a)} aria-label={`Edit ${a.destinationName}`}>Edit</button>
                  <button className={`${btn.text} text-red-700`} onClick={() => props.onDelete(a)} aria-label={`Delete ${a.destinationName}`}>✕</button>
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
      <footer className="flex items-center justify-between gap-2 px-4 pt-2 pb-3 text-sm">
        {readOnly ? <span /> : <button className={btn.ghost + ' !px-3 !py-1.5'} onClick={props.onAdd}>+ Add activity</button>}
        <span className="font-display font-semibold tabular-nums">{inr(day.totalCost)}</span>
      </footer>
    </section>
  )
}
