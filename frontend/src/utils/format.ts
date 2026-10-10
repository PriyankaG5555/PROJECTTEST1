const inrFormat = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
})

/** ₹1,23,456.5 — Indian digit grouping (frontend-spec.md §8). */
export const inr = (amount: number | null | undefined) => inrFormat.format(amount ?? 0)

const parse = (iso: string) => {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(Date.UTC(y, m - 1, d))
}
const part = (iso: string, opts: Intl.DateTimeFormatOptions) =>
  parse(iso).toLocaleDateString('en-GB', { ...opts, timeZone: 'UTC' })

/** "Sat, 14 Nov 2026" */
export const longDate = (iso: string) =>
  `${part(iso, { weekday: 'short' })}, ${part(iso, { day: 'numeric', month: 'short', year: 'numeric' })}`

/** "14 Nov" */
export const shortDate = (iso: string) => part(iso, { day: 'numeric', month: 'short' })

/** "10:00" + 90 min → "11:30" */
export const endTime = (time: string, minutes: number) => {
  const end = Number(time.slice(0, 2)) * 60 + Number(time.slice(3)) + minutes
  return `${String(Math.floor(end / 60)).padStart(2, '0')}:${String(end % 60).padStart(2, '0')}`
}

/** 90 → "1 h 30 min" */
export const durationLabel = (minutes: number) => {
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return [h && `${h} h`, m && `${m} min`].filter(Boolean).join(' ')
}

export const dayCount = (start: string, end: string) =>
  Math.round((parse(end).getTime() - parse(start).getTime()) / 86_400_000) + 1
