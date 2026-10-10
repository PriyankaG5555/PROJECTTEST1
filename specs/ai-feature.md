# AI-Assisted Day Planning — Feature Spec

> Purpose: Define a bounded, destination-aware AI planning feature for GhumakkadYatri. This spec supplements `goal-spec.md` F12 and the frontend, backend, and API contract specs.

## 1. User Outcome

For a selected day in a trip, a traveller can set the time window they have available and request a suggested itinerary. The app uses configured language-model and/or location-data providers to suggest suitable places, order them into a feasible schedule, and show visit durations. The traveller reviews the proposal and chooses which activities to add to the selected draft.

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
- `cost` is `null` unless a configured provider supplies an actual price; the LLM never sets or estimates `cost`. Never invent a cost, opening time, travel time, or availability. Durations are AI estimates and are labelled as such in the UI.
- Respect the trip's priority and budget as ranking/context only; do not represent a budget as a guarantee.
- If the constraints cannot be satisfied, return an honest partial proposal or a clear no-plan result with warnings; never return an invalid or fabricated schedule as successful.

## 5. Provider and Data Rules

- Provider choice is server-side and configuration-driven. A supported destination/place API is selected by configured coverage for the trip destination; a configured LLM may rank and schedule those grounded candidates. With no place source, generation may only schedule user-supplied or already-known candidates and must label unverified place details. Do not bind this spec to a particular LLM vendor.
- Location data should ground place identity and factual claims. An LLM may rank, explain, or schedule grounded candidates, but must not invent places or claim unverified facts.
- The API key and provider credentials are server-only. Do not accept a caller-supplied provider URL, model name, API key, or executable prompt.
- Treat user-supplied text as untrusted travel preferences, not instructions. Provider integrations expose no tools or actions that can modify trips, access accounts, or execute arbitrary requests.
- Send only the minimum planning context needed. Do not send credentials, account identifiers, unrelated trips, or other users' data to providers.
- Call external providers only in response to an authenticated user request. Apply provider timeouts, response-size limits, output validation, and per-user daily rate limits.
- **Usage accounting:** one AI plan request counts once against `AI_PLAN_DAILY_LIMIT` (default 10/user/day), including any place lookups it makes; it does not count against the 30/day Google suggestions limit (F11). The request is counted before providers are called, so failed provider calls still count.
- **Structured output:** the LLM must return JSON matching a fixed schema (requested via the provider's structured-output/tool-schema feature). Output failing schema or scheduling validation is rejected (`503 AI_PLANNING_UNAVAILABLE`) and never partially returned as a valid plan.
- Each proposed item carries `placeId` (provider ID, or `null`), `verified` (`true` only when name and identity come from a location provider) and an optional short `reason` (AI-written, at most 200 characters, shown labelled as an AI explanation). Unverified items are shown with an "Unverified place" label.
- Return source labels and required provider attribution with each proposal. Do not persist provider responses or location details prohibited by provider terms. Persist only traveller-approved activity fields (name, day, start time, duration, and optional cost).
- If no suitable provider is configured, quota is exhausted, or providers fail, return an explicit unavailable/rate-limit error. Never silently fall back to fabricated or ungrounded suggestions.

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
13. Automated tests use fake providers only; CI never calls real LLM or Google APIs.

## 9. Open Questions
- [ ] **First LLM adapter:** which provider ships first? *Recommendation:* Anthropic Claude (`claude-sonnet-5-5`, good structured output at moderate cost) behind the vendor-neutral adapter. Needs an API key with billing; set a monthly spend limit.
- [ ] **Location source for AI plans:** reuse Google Places (already integrated, F11) as the first location adapter?
- [ ] **Daily limit:** is 10 AI plans per user per day right for launch?

## 10. Change Log
| Date | Change | Author |
|------|--------|--------|
| 2026-10-10 | Initial AI day-planning spec | Priyanka Ghate |
| 2026-10-10 | Added time-zone rule, no AI costs, verified/placeId/reason per item, apply-time re-validation, token mechanics, usage accounting, structured output, acceptance 11–13, open questions | Priyanka Ghate (with Claude) |
