// Shapes from api-contract-spec.md §3.
export type TripType = 'solo' | 'couple' | 'family' | 'friends'
export type TripStatus = 'draft' | 'finalized'
export type Priority = 'high' | 'medium' | 'low'

export const TRIP_TYPES: Record<TripType, string> = {
  solo: 'Solo',
  couple: 'Couple',
  family: 'Family',
  friends: 'Friends',
}
export const PRIORITIES: Record<Priority, string> = { high: 'High', medium: 'Medium', low: 'Low' }

export interface User {
  id: string
  username: string
  createdAt: string
}

export interface Trip {
  id: string
  destination: string
  startDate: string
  endDate: string
  tripType: TripType
  status: TripStatus
  finalizedDraftId: string | null
  dayCount: number
  draftCount: number
  createdAt: string
  updatedAt: string
}

export interface DraftSummary {
  id: string
  name: string
  isFinal: boolean
  activityCount: number
  totalCost: number
  updatedAt: string
}

export interface TripDetail extends Trip {
  drafts: DraftSummary[]
}

export interface Activity {
  id: string
  dayNumber: number
  destinationName: string
  time: string | null
  cost: number | null
  priority: Priority | null
}

export interface Day {
  dayNumber: number
  date: string
  totalCost: number
  activities: Activity[]
}

export interface Draft {
  id: string
  tripId: string
  name: string
  isFinal: boolean
  totalCost: number
  days: Day[]
  createdAt: string
  updatedAt: string
}

export interface AffectedActivity {
  draftId: string
  draftName: string
  dayNumber: number
  activityId: string
  destinationName: string
}
