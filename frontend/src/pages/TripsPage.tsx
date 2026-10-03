import { Link, useNavigate } from 'react-router'
import { useTrips } from '../api/queries'
import { EmptyState, ErrorState, Spinner, StatusBadge, btn, card } from '../components/ui'
import { TRIP_TYPES } from '../types'
import { shortDate } from '../utils/format'

export default function TripsPage() {
  const trips = useTrips()
  const navigate = useNavigate()

  return (
    <>
      <div className="flex flex-wrap items-end gap-3">
        <div className="grid flex-1 gap-1">
          <h1 className="text-2xl font-bold">My trips</h1>
          <p className="text-sm text-slate-600">Open a trip to plan it day by day.</p>
        </div>
        <Link to="/trips/new" className={btn.primary}>
          + New trip
        </Link>
      </div>
      {trips.isPending && <Spinner />}
      {trips.isError && <ErrorState message={trips.error.message} onRetry={() => trips.refetch()} />}
      {trips.data?.length === 0 && (
        <EmptyState title="No trips yet">
          <p>Create your first trip to start planning.</p>
          <Link to="/trips/new" className={btn.primary}>
            + New trip
          </Link>
        </EmptyState>
      )}
      {!!trips.data?.length && (
        <ul className="grid grid-cols-[repeat(auto-fill,minmax(270px,1fr))] gap-4">
          {trips.data.map((t) => (
            <li key={t.id}>
              <button
                onClick={() => navigate(`/trips/${t.id}`)}
                className={`${card} grid w-full gap-2.5 p-4 text-left hover:border-brand-400 hover:shadow-md`}
              >
                <span className="flex items-start justify-between gap-2">
                  <span className="font-display text-lg font-semibold">{t.destination}</span>
                  <StatusBadge status={t.status} />
                </span>
                <span className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-slate-600">
                  <span>
                    {shortDate(t.startDate)} – {shortDate(t.endDate)}
                  </span>
                  <span>{t.dayCount} days</span>
                  <span>{TRIP_TYPES[t.tripType]}</span>
                </span>
                <span className="border-t border-dashed border-brand-200 pt-2 text-sm text-slate-600">
                  {t.draftCount} draft{t.draftCount > 1 ? 's' : ''}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </>
  )
}
