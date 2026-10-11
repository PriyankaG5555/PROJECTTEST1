# Accommodation (Stays) — Feature Spec

> Purpose: let travellers add where they stay each night, get free hotel suggestions, and make "Plan my day" start and end at that night's hotel. Supplements `goal-spec.md` F13 and `ai-feature.md`.

## 1. Decisions (2026-10-11)
| Topic | Decision |
|-------|----------|
| Model | **Stays by night range** on the **trip** (shared by all drafts): a stay covers nights from `checkInDay` to `checkOutDay` (check-out morning). Example 3-day trip: Panaji days 1→3 (2 nights), Calangute 3→4 (1 night). |
| Hotel data | **OpenStreetMap via Nominatim** (free, keyless): hotels, guest houses, hostels, resorts, apartments, motels near the destination. No prices or live availability. Attribution "© OpenStreetMap contributors". |
| Booking | Not in scope (NG1). Users book elsewhere; the app links to the place's website/map when known. |
| AI feature | Hotel suggestions are ordered by the trip's priority, and **Plan my day** uses that night's stay as the start/end point. |

## 2. Stays
- Fields: `name` (required, 1–100), `checkInDay` (1…dayCount), `checkOutDay` (checkInDay+1 … dayCount+1), optional `costPerNight` (INR, ≥ 0), optional map data from a suggestion (`placeId`, `lat`, `lon`, `address`, `url`, `kind`, `stars`). `verified` is true when the stay came from map data.
- Derived: `nights = checkOutDay − checkInDay`, `totalCost = nights × costPerNight` (null if no cost).
- Rules: stays may not overlap nights (`409 STAY_OVERLAP`); at most 10 stays per trip; the finalized lock applies (`409 TRIP_FINALIZED`); deleting a trip deletes its stays.
- Trip shortening: stays starting after the new last day are deleted, stays running past it are shortened. Deleted stays are listed in the same confirmation flow as activities (`details.affectedStays` of `ACTIVITIES_WOULD_BE_DELETED`).
- Budget: the planner's budget bar counts planned activities **plus** stays' total cost.
- PDF: each day shows "Night at <stay>" for the stay covering that night; the trip summary lists stays and their total.

## 3. Hotel suggestions
- `GET /trips/{id}/hotel-suggestions`: up to 15 places from Nominatim (`hotels in <destination>`, `guest houses in <destination>`, `hostels in <destination>`, with `extratags`), deduplicated, cached 7 days per destination (`place_cache`, key `hotels:<destination>`).
- Ordering by top priority: **Budget** → hostels, guest houses, then lower-star hotels; **Destinations** → closest to the destination's most notable places (from the place cache); **Time** → most central (closest to the average position of notable places); not set → stars (if known), then name.
- Each result: `placeId` (`osm:node/…`), `name`, `kind`, `stars` (if tagged), `address`, `website` (if tagged), `mapsUrl`, `lat`, `lon`, `distanceKm` (to the notable-places centre, when known).
- Counts against the per-user suggestions limit (30/day). Failure → `503 SUGGESTIONS_UNAVAILABLE`.

## 4. Plan my day with a hotel
- The stay for day *d* is the one with `checkInDay ≤ d < checkOutDay`; on the last day (check-out day) the stay with `checkOutDay = d` is used as the start point only.
- When the stay has coordinates: the first stop's travel time is measured from the hotel; the plan reserves travel time back to the hotel before the window ends (not on check-out day); candidates within 15 km of the hotel get a ranking bonus; reasons say "x km from your hotel".
- Response adds `startPoint` (`{ name, lat, lon }` or `null`). Warnings: "No hotel set for this night — travel from your hotel isn't included." / "Hotel location unknown — add it from suggestions to include travel."
- Request may set `"useStay": false` to ignore the hotel.

## 5. Acceptance criteria
1. A traveller can add, edit and delete stays; overlaps and out-of-range days are rejected with field errors or `STAY_OVERLAP`.
2. Hotel suggestions return real Nominatim places with attribution, ordered by priority (tested with fake data).
3. Plan my day for a night with a located stay starts with travel from the hotel and ends in time to return; reasons mention distance from the hotel.
4. Shortening a trip lists stays that would be deleted in the confirmation.
5. Budget bar and PDF include stays.

## 6. Change Log
| Date | Change | Author |
|------|--------|--------|
| 2026-10-11 | Initial spec: stays by night range, Nominatim hotel suggestions, hotel-aware Plan my day | Priyanka Ghate (with Claude) |
