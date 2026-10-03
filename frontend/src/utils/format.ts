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

export const dayCount = (start: string, end: string) =>
  Math.round((parse(end).getTime() - parse(start).getTime()) / 86_400_000) + 1
