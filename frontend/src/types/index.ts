// Shapes from api-contract-spec.md §3.
export type TripType = 'solo' | 'couple' | 'family' | 'friends'
export type TripStatus = 'draft' | 'finalized'
export type TopPriority = 'time' | 'destinations' | 'budget'

export const TRIP_TYPES: Record<TripType, string> = {
  solo: 'Solo',
  couple: 'Couple',
  family: 'Family',
  friends: 'Friends',
}
export const TOP_PRIORITIES: Record<TopPriority, string> = {
  time: 'Time',
  destinations: 'Destinations',
  budget: 'Budget',
}
/** Days with more activities than this are flagged as busy (goal-spec F8). */
export const BUSY_DAY_ACTIVITIES = 4

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
  topPriority: TopPriority | null
  budget: number | null
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

export interface Suggestion {
  placeId: string
  name: string
  address: string | null
  rating: number | null
  ratingCount: number | null
  priceLevel: string | null
  mapsUrl: string | null
}

export interface AffectedActivity {
  draftId: string
  draftName: string
  dayNumber: number
  activityId: string
  destinationName: string
}
