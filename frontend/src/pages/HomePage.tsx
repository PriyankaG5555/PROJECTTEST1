import { useQuery } from '@tanstack/react-query'

async function fetchHealth(): Promise<{ status: string }> {
  const res = await fetch('/api/v1/health')
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

/** Phase 0 placeholder: shows the brand and whether the API is reachable. */
export default function HomePage() {
  const health = useQuery({ queryKey: ['health'], queryFn: fetchHealth, retry: false })

  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col items-center justify-center gap-6 px-4 text-center">
      <img src="/logo.svg" alt="GhumakkadYatri" className="w-full max-w-sm" />
      <h1 className="text-2xl font-bold text-brand-700">Your trip planner is on its way</h1>
      <p className="text-brand-900">Plan your trip day by day and export a clean itinerary.</p>
      <p className="rounded-xl border border-brand-200 bg-white px-4 py-2 text-sm">
        API status:{' '}
        <span className="font-medium">
          {health.isPending ? 'checking…' : health.isSuccess ? health.data.status : 'not reachable'}
        </span>
      </p>
    </main>
  )
}
