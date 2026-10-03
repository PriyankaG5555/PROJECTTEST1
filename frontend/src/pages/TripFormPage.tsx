import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { ApiError, api } from '../api/client'
import { useRefreshData, useTrip } from '../api/queries'
import { useToast } from '../components/toast'
import { ConfirmDialog, ErrorState, Field, FormError, Spinner, btn, card, inputCls } from '../components/ui'
import { TOP_PRIORITIES, TRIP_TYPES, type AffectedActivity, type TopPriority, type TripDetail, type TripType } from '../types'
import { dayCount } from '../utils/format'

interface Values {
  destination: string
  startDate: string
  endDate: string
  tripType: TripType
  topPriority: TopPriority | ''
  budget: string
}

function validate(v: Values) {
  const e: Record<string, string> = {}
  if (!v.destination.trim()) e.destination = 'Enter a destination.'
  else if (v.destination.trim().length > 100) e.destination = 'Use at most 100 characters.'
  if (!v.startDate) e.startDate = 'Choose a start date.'
  if (!v.endDate) e.endDate = 'Choose an end date.'
  else if (v.startDate && v.endDate < v.startDate) e.endDate = 'End date must be on or after the start date.'
  else if (v.startDate && dayCount(v.startDate, v.endDate) > 30) e.endDate = 'A trip can be at most 30 days long.'
  const budget = Number(v.budget)
  if (v.budget !== '' && (Number.isNaN(budget) || budget < 0 || budget > 10_000_000))
    e.budget = 'Budget must be between ₹0 and ₹1,00,00,000.'
  return e
}

/** /trips/new and /trips/:tripId/edit */
export default function TripFormPage() {
  const { tripId } = useParams()
  const trip = useTrip(tripId ?? '')
  if (!tripId) return <TripForm />
  if (trip.isPending) return <Spinner />
  if (trip.isError) return <ErrorState message={trip.error.message} onRetry={() => trip.refetch()} />
  return <TripForm trip={trip.data} />
}

function TripForm({ trip }: { trip?: TripDetail }) {
  const [v, setV] = useState<Values>(
    trip
      ? {
          destination: trip.destination,
          startDate: trip.startDate,
          endDate: trip.endDate,
          tripType: trip.tripType,
          topPriority: trip.topPriority ?? '',
          budget: trip.budget?.toString() ?? '',
        }
      : { destination: '', startDate: '', endDate: '', tripType: 'solo', topPriority: '', budget: '' },
  )
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [formError, setFormError] = useState<string>()
  const [affected, setAffected] = useState<AffectedActivity[] | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()
  const refresh = useRefreshData()
  const toast = useToast()
  const set = (k: keyof Values) => (e: { target: { value: string } }) => {
    setV({ ...v, [k]: e.target.value })
    setAffected(null)
  }

  async function save(confirmDeleteActivities = false) {
    const found = validate(v)
    setErrors(found)
    setFormError(undefined)
    if (Object.keys(found).length) return
    setBusy(true)
    const body = {
      ...v,
      destination: v.destination.trim(),
      topPriority: v.topPriority || null,
      budget: v.budget === '' ? null : Number(v.budget),
    }
    try {
      if (trip) {
        const res = await api<{ deletedActivityCount: number }>(`/trips/${trip.id}`, 'PATCH', {
          ...body,
          confirmDeleteActivities,
        })
        await refresh()
        toast(res.deletedActivityCount ? `Trip saved. ${res.deletedActivityCount} activities deleted.` : 'Trip saved')
        navigate(`/trips/${trip.id}`)
      } else {
        const res = await api<{ trip: TripDetail }>('/trips', 'POST', body)
        await refresh()
        toast('Trip created with Draft 1')
        navigate(`/trips/${res.trip.id}`)
      }
    } catch (err) {
      if (err instanceof ApiError && err.code === 'ACTIVITIES_WOULD_BE_DELETED')
        setAffected((err.details?.affected as AffectedActivity[]) ?? [])
      else if (err instanceof ApiError && Object.keys(err.fields).length) setErrors(err.fields)
      else setFormError(err instanceof Error ? err.message : 'Something went wrong.')
    } finally {
      setBusy(false)
    }
  }

  async function deleteTrip() {
    if (!trip) return
    setBusy(true)
    try {
      await api(`/trips/${trip.id}`, 'DELETE')
      await refresh()
      toast('Trip deleted')
      navigate('/trips')
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Something went wrong.')
      setConfirmDelete(false)
      setBusy(false)
    }
  }

  const submit = (e: FormEvent) => {
    e.preventDefault()
    void save(affected !== null)
  }

  return (
    <>
      <div className="grid gap-1">
        <h1 className="text-2xl font-bold">{trip ? 'Edit trip' : 'New trip'}</h1>
        <p className="text-sm text-slate-600">
          {trip
            ? 'Shortening a trip deletes activities on the removed days. You’ll see them before anything is deleted.'
            : 'Trips can be 1 to 30 days. You’ll plan each day next.'}
        </p>
      </div>
      <form className={`${card} grid max-w-xl gap-4 p-5`} onSubmit={submit} noValidate>
        <Field id="destination" label="Destination" error={errors.destination}>
          <input id="destination" className={inputCls} maxLength={100} placeholder="e.g. Rishikesh"
            value={v.destination} onChange={set('destination')} autoFocus />
        </Field>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field id="startDate" label="Start date" error={errors.startDate}>
            <input id="startDate" type="date" className={inputCls} value={v.startDate} onChange={set('startDate')} />
          </Field>
          <Field id="endDate" label="End date" error={errors.endDate}>
            <input id="endDate" type="date" className={inputCls} value={v.endDate} onChange={set('endDate')} />
          </Field>
        </div>
        <Field id="tripType" label="Trip type" error={errors.tripType}>
          <select id="tripType" className={inputCls} value={v.tripType} onChange={set('tripType')}>
            {Object.entries(TRIP_TYPES).map(([k, label]) => (
              <option key={k} value={k}>
                {label}
              </option>
            ))}
          </select>
        </Field>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field id="topPriority" label={<>Top priority <span className="font-normal text-slate-500">(optional)</span></>}
            error={errors.topPriority} hint="What matters most when time, places or money run short?">
            <select id="topPriority" className={inputCls} value={v.topPriority} onChange={set('topPriority')}>
              <option value="">Not set</option>
              {Object.entries(TOP_PRIORITIES).map(([k, label]) => (
                <option key={k} value={k}>
                  {label}
                </option>
              ))}
            </select>
          </Field>
          <Field id="budget" label={<>Budget in ₹ <span className="font-normal text-slate-500">(optional)</span></>}
            error={errors.budget}>
            <input id="budget" type="number" min="0" step="1" inputMode="numeric" className={inputCls}
              value={v.budget} onChange={set('budget')} placeholder="e.g. 25000" />
          </Field>
        </div>
        {affected && (
          <div className="grid gap-1.5 rounded-xl bg-amber-50 p-3 text-sm text-amber-900" role="alert">
            <b>
              Shortening this trip will delete {affected.length} activit{affected.length === 1 ? 'y' : 'ies'}:
            </b>
            <ul className="list-disc pl-5">
              {affected.map((a) => (
                <li key={a.activityId}>
                  {a.draftName} · Day {a.dayNumber}: {a.destinationName}
                </li>
              ))}
            </ul>
          </div>
        )}
        <FormError message={formError} />
        <div className="flex flex-wrap items-center gap-2">
          <button className={affected ? btn.danger : btn.primary} disabled={busy}>
            {affected ? `Delete ${affected.length} and save` : trip ? 'Save changes' : 'Create trip'}
          </button>
          <Link to={trip ? `/trips/${trip.id}` : '/trips'} className={btn.ghost}>
            Cancel
          </Link>
          {trip && (
            <button type="button" className={`${btn.text} ml-auto text-red-700`} onClick={() => setConfirmDelete(true)}>
              Delete trip
            </button>
          )}
        </div>
      </form>
      {confirmDelete && trip && (
        <ConfirmDialog
          title="Delete this trip?"
          message={`${trip.destination} and all its drafts and activities will be deleted.`}
          confirmLabel="Delete trip"
          danger
          busy={busy}
          onConfirm={deleteTrip}
          onClose={() => setConfirmDelete(false)}
        />
      )}
    </>
  )
}
