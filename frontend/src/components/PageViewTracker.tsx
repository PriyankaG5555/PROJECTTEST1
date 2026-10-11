import { useEffect } from 'react'
import { useLocation } from 'react-router'
import { api } from '../api/client'
import { useMe } from '../api/queries'

const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi

/** "/trips/3f2…/compare" -> "/trips/:tripId/compare" (no IDs leave the browser). */
export function routeTemplate(pathname: string): string {
  return pathname.replace(/^\/trips\/[^/]+/, (m) => (m === '/trips/new' ? m : '/trips/:tripId')).replace(UUID, ':id')
}

/** Logged-in page views for observability (observability-spec.md §3). Fire-and-forget. */
export default function PageViewTracker() {
  const { pathname } = useLocation()
  const me = useMe()
  const loggedIn = Boolean(me.data)
  useEffect(() => {
    if (!loggedIn) return
    api('/telemetry/page-view', 'POST', { route: routeTemplate(pathname) }).catch(() => undefined)
  }, [pathname, loggedIn])
  return null
}
