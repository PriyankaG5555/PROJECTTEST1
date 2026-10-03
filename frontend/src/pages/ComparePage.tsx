import { Link, useParams, useSearchParams } from 'react-router'
import { useDraft, useTrip } from '../api/queries'
import { ErrorState, Spinner, btn, card, inputCls } from '../components/ui'
import type { Day, Draft } from '../types'
import { inr, shortDate } from '../utils/format'

/** Side-by-side draft comparison (frontend-spec.md Flow 4, P2). */
export default function ComparePage() {
  const { tripId = '' } = useParams()
  const [params, setParams] = useSearchParams()
  const trip = useTrip(tripId)
  const drafts = trip.data?.drafts ?? []
  const aId = params.get('a') ?? drafts[0]?.id
  const bId = params.get('b') ?? drafts.find((d) => d.id !== aId)?.id
  const a = useDraft(aId)
  const b = useDraft(bId)

  if (trip.isPending) return <Spinner />
  if (trip.isError) return <ErrorState message={trip.error.message} onRetry={() => trip.refetch()} />
  const t = trip.data
  const pick = (key: 'a' | 'b') => (e: { target: { value: string } }) =>
    setParams({ a: aId ?? '', b: bId ?? '', [key]: e.target.value }, { replace: true })

  return (
    <>
      <div>
        <Link to={`/trips/${t.id}`} className={btn.text}>← Back to planner</Link>
      </div>
      <div className="grid gap-1">
        <h1 className="text-2xl font-bold">Compare drafts</h1>
        <p className="text-sm text-slate-600">{t.destination} · {t.dayCount} days. Pick two drafts to see them side by side.</p>
      </div>
      <div className="flex flex-wrap gap-3">
        {(['a', 'b'] as const).map((key) => (
          <label key={key} className="grid min-w-44 flex-1 gap-1 text-sm font-medium">
            Draft {key.toUpperCase()}
            <select className={inputCls} value={(key === 'a' ? aId : bId) ?? ''} onChange={pick(key)}>
              {drafts.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          </label>
        ))}
      </div>
      {(a.isPending || b.isPending) && <Spinner />}
      {(a.isError || b.isError) && <ErrorState message="Couldn't load the drafts." onRetry={() => { a.refetch(); b.refetch() }} />}
      {a.data && b.data && <CompareTable tripId={t.id} a={a.data} b={b.data} />}
    </>
  )
}

function DayCell({ day }: { day: Day }) {
  if (!day.activities.length) return <span className="text-slate-500">No activities</span>
  return (
    <>
      <ul className="grid gap-1 text-sm">
        {day.activities.map((x) => (
          <li key={x.id}>
            <b className="tabular-nums">{x.time ?? '—'}</b> {x.destinationName}
            {x.cost !== null && <span className="text-slate-600 tabular-nums"> · {inr(x.cost)}</span>}
          </li>
        ))}
      </ul>
      <div className="mt-1.5 text-sm text-slate-600 tabular-nums">Day total {inr(day.totalCost)}</div>
    </>
  )
}

function CompareTable({ tripId, a, b }: { tripId: string; a: Draft; b: Draft }) {
  const cheaper = (x: number, y: number) =>
    x < y ? <span className="ml-1.5 text-xs font-bold text-green-700">Cheaper by {inr(y - x)}</span> : null
  const cell = 'border-b border-brand-200 px-3 py-2.5 text-left align-top'
  return (
    <div className={`${card} overflow-x-auto`}>
      <table className="w-full min-w-[560px] border-collapse">
        <thead className="bg-brand-50 font-display">
          <tr>
            <th className={cell} scope="col">Day</th>
            <th className={cell} scope="col">{a.name}</th>
            <th className={cell} scope="col">{b.name}</th>
          </tr>
        </thead>
        <tbody>
          {a.days.map((day, i) => (
            <tr key={day.dayNumber}>
              <td className={`${cell} font-semibold whitespace-nowrap`}>
                Day {day.dayNumber}
                <div className="text-sm font-normal text-slate-600">{shortDate(day.date)}</div>
              </td>
              <td className={cell}><DayCell day={day} /></td>
              <td className={cell}>{b.days[i] && <DayCell day={b.days[i]} />}</td>
            </tr>
          ))}
        </tbody>
        <tfoot className="font-display font-bold">
          <tr>
            <td className={cell}>Trip total</td>
            <td className={`${cell} tabular-nums`}>{inr(a.totalCost)}{cheaper(a.totalCost, b.totalCost)}</td>
            <td className={`${cell} tabular-nums`}>{inr(b.totalCost)}{cheaper(b.totalCost, a.totalCost)}</td>
          </tr>
          <tr>
            <td className="px-3 py-2.5" />
            {[a, b].map((d) => (
              <td key={d.id} className="px-3 py-2.5">
                <Link to={`/trips/${tripId}?draft=${d.id}`} className={`${btn.ghost} !px-3 !py-1.5`}>Open this draft</Link>
              </td>
            ))}
          </tr>
        </tfoot>
      </table>
    </div>
  )
}
