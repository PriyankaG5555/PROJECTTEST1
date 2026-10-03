import { useQueryClient } from '@tanstack/react-query'
import { Link, NavLink, Navigate, Outlet, useLocation, useNavigate } from 'react-router'
import { api } from '../api/client'
import { keys, useMe } from '../api/queries'
import { ErrorState, Spinner } from './ui'

/** Redirects to /login?next=… when there is no session (frontend-spec.md §9). */
export function RequireAuth({ children }: { children: React.ReactNode }) {
  const me = useMe()
  const location = useLocation()
  if (me.isPending) return <Spinner />
  if (me.isError) return <ErrorState message={me.error.message} onRetry={() => me.refetch()} />
  if (!me.data) return <Navigate to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`} replace />
  return children
}

/** Logged-in users skip the login/signup pages. */
export function GuestOnly({ children }: { children: React.ReactNode }) {
  const me = useMe()
  if (me.isPending) return <Spinner />
  if (me.data) return <Navigate to="/trips" replace />
  return children
}

const navCls = ({ isActive }: { isActive: boolean }) =>
  `rounded-lg px-3 py-1.5 font-medium ${isActive ? 'bg-brand-50 text-brand-900' : 'text-slate-600 hover:text-brand-900'}`

export function AppLayout() {
  const me = useMe()
  const qc = useQueryClient()
  const navigate = useNavigate()

  async function logout() {
    await api('/auth/logout', 'POST').catch(() => undefined)
    qc.clear()
    qc.setQueryData(keys.me, null)
    navigate('/login', { state: { notice: "You've been logged out." } })
  }

  return (
    <>
      <header className="sticky top-0 z-10 border-b border-brand-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-3 px-4 py-2.5">
          <Link to="/trips" className="flex items-center gap-2" aria-label="GhumakkadYatri home">
            <img src="/favicon.svg" alt="" className="size-10" />
            <span className="font-display text-xl font-bold tracking-tight text-brand-700">
              Ghumakkad<span className="text-brand-400">Yatri</span>
            </span>
          </Link>
          <span className="flex-1" />
          <nav className="flex flex-wrap gap-1" aria-label="Main">
            <NavLink to="/trips" end={false} className={navCls}>
              My trips
            </NavLink>
            <NavLink to="/account" className={navCls}>
              {me.data?.username ?? 'Account'}
            </NavLink>
            <button onClick={logout} className="rounded-lg px-3 py-1.5 font-medium text-slate-600 hover:text-brand-900">
              Log out
            </button>
          </nav>
        </div>
      </header>
      <main className="mx-auto grid max-w-6xl gap-5 px-4 pt-6 pb-16">
        <Outlet />
      </main>
    </>
  )
}
