# AI-Assisted Day Planning — Feature Spec

> Purpose: Define a bounded, destination-aware AI planning feature for GhumakkadYatri. This spec supplements `goal-spec.md` F12 and the frontend, backend, and API contract specs.

## 1. User Outcome

For a selected day in a trip, a traveller can set the time window they have available and request a suggested itinerary. The app uses free, open data (Wikipedia places located with OpenStreetMap) and a rule-based planner in our own code to suggest suitable places, order them into a feasible schedule, and show visit durations. **No API keys and no paid or LLM services are used** (decided 2026-10-10). The traveller reviews the proposal and chooses which activities to add to the selected draft.

This is a planning aid, not a booking service, live availability guarantee, or general-purpose chat assistant.

## 2. Scope

### In scope
- Generate a proposal for one selected trip day at a time.
- Use the trip's destination, date, priority, and budget, plus the selected draft's existing activities as context.
- Let the traveller provide a local-time start/end window, interests, must-visit places, and places to avoid.
- Return a time-ordered list of place/activity suggestions with proposed start times, visit durations, optional costs, source/attribution, and any scheduling caveats.
- Let the traveller selectively add suggestions to the draft. Save selected items together atomically.
- Persist optional activity duration in minutes so the planned end time remains visible after reload and export.

### Out of scope
- Open-ended AI chat, non-travel questions, bookings, payments, reservations, or guaranteed availability.
- Automatically changing, deleting, or replacing existing activities.
- Generating a single itinerary spanning multiple trip days in one request.
- Claiming exact opening hours, travel times, ticket prices, or accessibility unless a configured source explicitly provides them.

## 3. User Flow

1. In an editable trip draft, the traveller selects a day and opens **Plan this day with AI**.
2. The form shows the selected destination and date and requires a start and end time in destination-local time. Interests, must-visit places, and places to avoid are optional and bounded travel-planning inputs. Existing activities are always retained and treated as fixed schedule constraints.
3. The traveller requests a plan. The UI shows a loading state and does not save any generated content yet.
4. The preview shows ordered suggestions, start time, visit duration and derived end time, optional cost, source/attribution, and warnings. The traveller may deselect suggestions or request a new proposal.
5. The traveller selects **Add selected to plan**. The selected items are validated and added to the current draft in one operation. The planner refreshes from the server.
6. Closing or dismissing the preview leaves the draft unchanged. Provider errors show a clear retry message; manual planning remains available.

The feature is unavailable for finalized trips. Reopening the trip restores the normal editable planning flow.

## 4. Inputs and Scheduling Rules

- The day number must exist in the trip; the destination and date come from the server-owned trip.
- `startTime` and `endTime` are required `HH:mm` 24-hour local times, with `endTime` strictly after `startTime`. Overnight windows are not supported.
- All times are **wall-clock times at the destination**, the same convention as existing activity times. Trips store no time zone and the server performs no time-zone conversion.
- Interests are optional (up to 5 entries, 60 characters each); must-visit and avoid lists are optional (up to 10 entries each, 100 characters per place name). They are travel constraints, not arbitrary prompts.
- Existing activities are always included as fixed schedule constraints. The service must not move them. If their known time/duration conflicts with the requested window, return warnings and do not silently omit or reschedule them.
- If an existing timed activity has no duration, its end time is unknown; conservatively treat the remainder of the requested window after its start as unavailable and explain that the traveller can add a duration and regenerate. Untimed activities do not occupy a calculated time slot.
- Proposed activities must fit within the requested window and must not overlap one another or fixed existing activities. Include realistic travel buffers only when supported by a configured location provider; otherwise disclose that transfer time is not verified.
- `durationMinutes` is a positive integer for timed proposed activities. The displayed end time is derived from start time plus duration; end time is not stored as a separate field.
- Return no more than 10 proposed activities for one day.
- `cost` is always `null` in proposals; the planner never sets or estimates `cost`. Never invent a cost, opening time or availability. Durations and travel times are estimates and are labelled as such in the UI.
- Respect the trip's priority and budget as ranking/context only; do not represent a budget as a guarantee.
- If the constraints cannot be satisfied, return an honest partial proposal or a clear no-plan result with warnings; never return an invalid or fabricated schedule as successful.

## 5. Provider and Data Rules

- **Place data (free, keyless):** OpenStreetMap **Nominatim** finds the destination and its area; **Wikipedia** lists notable places with coordinates — GeoSearch within 10 km of the centre (five points across large areas such as states, capped at 1°) plus the "Tourist attractions in <place>" category and its attraction-type sub-categories (beaches, forts, temples, churches, museums, parks…). Pages are kept only when their description/title or sub-category marks an attraction (towns, rivers, institutions are dropped). Must-visit names not found this way are looked up on Wikipedia by name (within ~150 km). Calls are server-side with an identifying User-Agent and results are **cached per destination for 7 days** (`place_cache`). (Overpass API was evaluated and rejected: its public servers timed out on area queries.)
- **Planner (no LLM):** deterministic rules in `planner_service`. Ranking: must-visit places first; then by the trip's top priority — **Destinations**: most notable first (Wikipedia/Wikidata/heritage tags); **Budget**: free places first (beaches, parks, `fee=no`), then notability; **Time**: at most 3 stops, nearest-next routing; not set: notability — plus a bonus for places matching the traveller's interests (keyword → category map, e.g. museums, history, beaches, nature, temples/churches). Avoided names are excluded. Visit durations come from a fixed table per category (e.g. museum 120 min, fort/castle/palace 90, beach 120, waterfall 120, place of worship 45, viewpoint 30, park 60). Travel time between stops = straight-line distance at ~25 km/h + 10 min, rounded up to 5 min. After the first stop the planner picks the nearest of the next 4 ranked places (Time: nearest of all) to reduce travel. Items are placed in the earliest free slot inside the window that does not overlap fixed activities or other items; places that do not fit are skipped. At most 4 items, so a planned day never triggers the busy-day flag (Time priority: 3); must-visit places may raise this up to 10.
- No credentials are involved. The server builds all map queries itself; callers cannot supply URLs, queries or endpoints.
- Treat user-supplied text as untrusted travel preferences, not instructions: interests are only matched against a fixed keyword list; place names are only compared with map names.
- Send only the destination name and must-visit place names to Nominatim/Wikipedia. Never send user, trip or account data.
- Call external providers only in response to an authenticated user request. Apply provider timeouts, response-size limits, output validation, and per-user daily rate limits.
- **Usage accounting:** one plan request counts once against `AI_PLAN_DAILY_LIMIT` (default 10/user/day) and does not count against the 30/day suggestions limit (F11). The request is counted before map data is fetched, so failed lookups still count.
- **Hotel (accommodation-feature.md §4):** when a stay covers the night, the plan starts at the hotel (travel to the first stop), reserves travel back before the window ends (not on check-out day), and ranks places within 15 km of the hotel higher. Response `startPoint` names the hotel.
- **Grounding:** every proposed place is either a Wikipedia place with coordinates (`verified: true`, `placeId` like `wikipedia:12345`, map link to openstreetmap.org at its coordinates) or one of the traveller's must-visit names that could not be found on the map (`verified: false`, no location; placed without a travel estimate and labelled "Unverified place"). The planner cannot invent places.
- Each proposed item carries `placeId` (provider ID, or `null`), `verified` (`true` only when name and identity come from a location provider) and an optional short `reason` (AI-written, at most 200 characters, shown labelled as an AI explanation). Unverified items are shown with an "Unverified place" label.
- Return source labels and required attribution with each proposal: `source: "Wikipedia"` and `attribution: "Places: Wikipedia (CC BY-SA) · Location: © OpenStreetMap contributors"` (required by CC BY-SA and ODbL). Do not persist provider responses or location details prohibited by provider terms. Persist only traveller-approved activity fields (name, day, start time, duration, and optional cost).
- If the map services fail or time out, return `503 AI_PLANNING_UNAVAILABLE`. If the destination cannot be found on the map, return a proposal containing only the traveller's must-visit places (unverified) with a warning. Never fabricate places.

## 6. Persistence and Compatibility

- Add nullable `duration_minutes` to activities; existing activities and clients remain valid with `null`.
- Keep the existing activity start-time semantics. Derive and display the end time only when both start time and duration are present.
- AI generation returns a transient proposal and does not create a database record. The short-lived signed proposal token contains the canonical activity fields and is bound to the user, trip, draft, day, and proposed item IDs; the bulk-apply endpoint accepts only selected IDs from that token. Applying the token is single-use and adds selected items in one transaction.
- Enforce existing ownership and finalized-trip rules for both generation and apply operations. A proposal cannot be applied to a different trip or draft.
- **Re-check at apply time.** The draft may have changed after generation. When applying, the server re-validates the selected items against the day's *current* activities and the trip's *current* dates. If any selected item now overlaps a timed activity or the day no longer exists, nothing is added and the server returns `409 AI_PROPOSAL_INVALID` ("This plan is out of date — generate a new one").
- **Token mechanics.** The proposal token is an HMAC-signed token (server secret, `typ: "ai_proposal"`, 15-minute expiry) carrying `proposal_id`, user, trip, draft, day and the canonical items. Applied `proposal_id`s are recorded in `ai_plan_applications`; rows older than 1 day are deleted opportunistically.
- PDF exports should include duration/end time when present and retain the existing output for activities without duration.

## 7. Privacy, Safety, and UX

- The feature is an action within the trip planner, not an unrestricted conversation interface.
- Clearly label output as AI-assisted suggestions and estimates; the traveller remains responsible for verifying details with venues.
- Show provider attribution as required. Distinguish verified source data from AI-generated ordering or explanatory text.
- Do not log raw user-provided interests/place lists, provider prompts/responses, API keys, or credentials. Structured operational logs may include request ID, provider identifier, latency, outcome, and rate-limit counters.
- Provide accessible labels, keyboard operation, loading, empty, partial-result, unavailable, and retry states. Keep ordinary add/edit activity controls usable when AI is unavailable.
- Respect reduced-motion preferences and existing responsive/mobile UI behavior.

## 8. Acceptance Criteria

1. A signed-in user can request a plan only for an owned trip and valid day; another user's trip returns `404`.
2. A request with invalid or reversed times is rejected with field-level validation errors.
3. Given a valid time window, the proposal contains only timed activities that fit within it; proposed activities do not overlap each other or fixed existing activities. An existing timed activity with unknown duration is handled conservatively with a warning.
4. Every proposed activity has a place/activity name and positive duration; its end time is derived correctly. Unknown costs remain `null`.
5. Provider facts and attribution are surfaced, estimates are labeled, and unverified hours/travel times are not presented as confirmed.
6. Generation, closing the preview, and failed provider calls do not mutate the draft.
7. Applying selected items adds only those items, including their start times and durations, in one transaction; a failure adds none.
8. Applying to a finalized trip returns `409 TRIP_FINALIZED`; a different or unowned draft cannot receive the proposal.
9. Missing/unavailable providers and exhausted limits produce explicit errors, with manual planning unaffected.
10. Existing activities without duration continue to load, sort, edit, and export unchanged.
11. If the draft changes after generation so that a selected item now overlaps a timed activity (or its day no longer exists), applying returns `409 AI_PROPOSAL_INVALID` and adds nothing.
12. Proposed items never carry an AI-invented cost; `verified: false` items are labelled "Unverified place".
13. Automated tests use fake map data only; CI never calls Nominatim or Wikipedia. Planner rules (ranking, durations, travel buffers, window and overlap handling) have unit tests.

## 9. Open Questions
- [x] **Provider:** **Decided 2026-10-10:** no API keys, no LLM. Nominatim (OpenStreetMap) + Wikipedia places with a rule-based planner. Endpoint names keep the `ai-` prefix for compatibility; the UI calls the feature **"Plan my day"**.
- [x] **Location source:** Wikipedia places located via OpenStreetMap Nominatim; Google Places removed; Overpass rejected (unreliable public servers).
- [ ] **Daily limit:** is 10 AI plans per user per day right for launch?

## 10. Change Log
| Date | Change | Author |
|------|--------|--------|
| 2026-10-10 | Initial AI day-planning spec | Priyanka Ghate |
| 2026-10-10 | Switched to OpenStreetMap + rule-based planner (no API keys, no LLM); place cache; OSM attribution; travel-time estimates | Priyanka Ghate (with Claude) |
| 2026-10-10 | Added time-zone rule, no AI costs, verified/placeId/reason per item, apply-time re-validation, token mechanics, usage accounting, structured output, acceptance 11–13, open questions | Priyanka Ghate (with Claude) |
