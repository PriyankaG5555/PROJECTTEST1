import { useQuery, useQueryClient } from '@tanstack/react-query'
import type { Draft, Trip, TripDetail, User } from '../types'
import { ApiError, api } from './client'

export const keys = {
  me: ['me'] as const,
  trips: ['trips'] as const,
  trip: (id: string) => ['trip', id] as const,
  draft: (id: string) => ['draft', id] as const,
}

/** Current user, or null when not logged in. */
export function useMe() {
  return useQuery({
    queryKey: keys.me,
    queryFn: async () => {
      try {
        return (await api<{ user: User }>('/auth/me')).user
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) return null
        throw e
      }
    },
    staleTime: Infinity,
  })
}

export const useTrips = () =>
  useQuery({
    queryKey: keys.trips,
    queryFn: async () => (await api<{ trips: Trip[] }>('/trips')).trips,
  })

export const useTrip = (id: string) =>
  useQuery({
    queryKey: keys.trip(id),
    queryFn: async () => (await api<{ trip: TripDetail }>(`/trips/${id}`)).trip,
    enabled: Boolean(id),
  })

export const useDraft = (id: string | undefined) =>
  useQuery({
    queryKey: keys.draft(id ?? ''),
    queryFn: async () => (await api<{ draft: Draft }>(`/drafts/${id}`)).draft,
    enabled: Boolean(id),
  })

/** After any change, refetch everything except the current user (small app, simple rule). */
export function useRefreshData() {
  const qc = useQueryClient()
  return () => qc.invalidateQueries({ predicate: (q) => q.queryKey[0] !== 'me' })
}
