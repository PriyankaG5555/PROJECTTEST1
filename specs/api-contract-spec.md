# API Contract Spec — Trip Planner (GhumakkadYatri)

> Purpose: The single source of truth between frontend and backend. Both sides must conform exactly to this contract.

## 1. General Conventions
- **Base URL:** `/api/v1` (all paths below are relative to it). Dev: `http://localhost:8000/api/v1`.
- **Protocol / format:** REST over HTTPS; JSON request and response bodies (`Content-Type: application/json`), except the PDF export.
- **Authentication:** Session cookie `gy_session` (JWT) set by the server on signup/login — `HttpOnly`, `Secure`, `SameSite=Lax`, `Path=/`, 7-day expiry. Browsers send it automatically (`credentials: "include"`). Endpoints marked **Auth: Yes** return `401` without a valid cookie.
- **CSRF protection:** `SameSite=Lax` cookie + mutating requests (`POST`/`PATCH`/`DELETE`) must send `Content-Type: application/json`; CORS allows only the frontend origin, with credentials.
- **Naming convention:** camelCase for JSON fields; kebab-free lowercase paths.
- **IDs:** UUID v4 strings.
- **Date/time format:**
  - Dates: `YYYY-MM-DD` (e.g. `2026-11-14`), no timezone — they are the traveller's local calendar dates.
  - Activity time: `HH:mm` 24-hour (e.g. `09:30`).
  - Timestamps (`createdAt`, `updatedAt`): ISO 8601 UTC (e.g. `2026-10-03T10:15:00Z`).
- **Money:** JSON number in INR, up to 2 decimals (e.g. `1250.5`). No currency field — INR is fixed.
- **Ownership:** Users can only access their own trips, drafts and activities. Another user's resource returns `404 NOT_FOUND` (not `403`) so its existence is not revealed.
- **Finalized lock:** While a trip is `finalized`, every change to it, its drafts, or its activities returns `409 TRIP_FINALIZED`, except **reopen**, **export** and **delete trip**.
- **Pagination:** None in MVP (a user's trips list is small). Lists return all items.
- **Versioning:** URL prefix `/api/v1`. Breaking changes require `/api/v2`.
- **Null vs missing:** Optional fields are always present in responses, with `null` when empty. In `PATCH` requests, an omitted field is left unchanged; `null` clears it.

## 2. Standard Error Response
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "End date must be on or after start date.",
    "details": {
      "fields": { "endDate": "Must be on or after startDate" }
    }
  }
}
```
`message` is safe to show to the user. `details` is optional and depends on the code.

| HTTP status | Code | When |
|-------------|------|------|
| 400 | VALIDATION_ERROR | Body/params fail validation; `details.fields` maps field → message |
| 401 | UNAUTHORIZED | Missing/expired/invalid session cookie |
| 401 | INVALID_CREDENTIALS | Wrong username or password on login |
| 404 | NOT_FOUND | Resource doesn't exist or belongs to another user |
| 409 | USERNAME_TAKEN | Signup with an existing username (case-insensitive) |
| 409 | TRIP_FINALIZED | Change attempted on a finalized trip (reopen first) |
| 409 | TRIP_NOT_FINALIZED | Export or reopen on a draft trip |
| 409 | ACTIVITIES_WOULD_BE_DELETED | Trip date change would delete activities and was not confirmed; `details.affected` lists them |
| 409 | DRAFT_NAME_TAKEN | Draft name already used in this trip |
| 409 | LAST_DRAFT | Deleting the only draft of a trip |
| 409 | DRAFT_LIMIT_REACHED | Creating more than 5 drafts in a trip |
| 429 | RATE_LIMITED | More than 10 signup/login/delete-account attempts per minute from one IP |
| 500 | INTERNAL_ERROR | Unexpected server error (no internal details exposed) |

## 3. Shared Schemas

### User
```json
{
  "id": "6f1c2a9e-1b2c-4d3e-8f90-123456789abc",
  "username": "riya_travels",
  "createdAt": "2026-10-03T10:15:00Z"
}
```

### Trip
```json
{
  "id": "0b8e7c1a-...",
  "destination": "Goa",
  "startDate": "2026-11-14",
  "endDate": "2026-11-17",
  "tripType": "friends",
  "status": "draft",
  "finalizedDraftId": null,
  "dayCount": 4,
  "draftCount": 2,
  "createdAt": "2026-10-03T10:15:00Z",
  "updatedAt": "2026-10-03T11:02:00Z"
}
```
| Field | Type | Rules |
|-------|------|-------|
| destination | string | Required, 1–100 chars, trimmed |
| startDate, endDate | date | Required; `endDate ≥ startDate`; trip length (`dayCount`) 1–30 days |
| tripType | enum | `solo` \| `couple` \| `family` \| `friends` |
| status | enum | `draft` \| `finalized` (read-only; changed only via finalize/reopen) |
| finalizedDraftId | uuid \| null | Set when finalized; `null` when draft |
| dayCount | integer | Read-only; `endDate − startDate + 1` |
| draftCount | integer | Read-only |

### TripDetail
`Trip` plus the list of its drafts (without activities):
```json
{
  "...all Trip fields": "...",
  "drafts": [
    { "id": "d1...", "name": "Draft 1", "isFinal": false, "activityCount": 6, "totalCost": 8400, "updatedAt": "2026-10-03T11:02:00Z" },
    { "id": "d2...", "name": "Hills plan", "isFinal": false, "activityCount": 3, "totalCost": 5100, "updatedAt": "2026-10-03T10:40:00Z" }
  ]
}
```

### DraftSummary
| Field | Type | Notes |
|-------|------|-------|
| id | uuid | |
| name | string | 1–50 chars, unique within the trip (case-insensitive) |
| isFinal | boolean | `true` for the draft the trip was finalized from |
| activityCount | integer | |
| totalCost | number | Sum of all activity costs (nulls count as 0) |
| updatedAt | timestamp | |

### Draft
Full draft with Day 1 … Day N (always exactly `trip.dayCount` days, including empty ones):
```json
{
  "id": "d1...",
  "tripId": "0b8e7c1a-...",
  "name": "Draft 1",
  "isFinal": false,
  "totalCost": 8400,
  "days": [
    {
      "dayNumber": 1,
      "date": "2026-11-14",
      "totalCost": 2300,
      "activities": [
        { "id": "a1...", "dayNumber": 1, "destinationName": "Baga Beach", "time": "09:30", "cost": 0, "priority": "high" },
        { "id": "a2...", "dayNumber": 1, "destinationName": "Fort Aguada", "time": "15:00", "cost": 300, "priority": "medium" },
        { "id": "a3...", "dayNumber": 1, "destinationName": "Seafood dinner", "time": null, "cost": 2000, "priority": null }
      ]
    },
    { "dayNumber": 2, "date": "2026-11-15", "totalCost": 0, "activities": [] }
  ],
  "createdAt": "2026-10-03T10:15:00Z",
  "updatedAt": "2026-10-03T11:02:00Z"
}
```
Activities in each day are sorted by `time` ascending; activities with `time: null` come last (then by creation order).

### Activity
| Field | Type | Rules |
|-------|------|-------|
| id | uuid | Read-only |
| dayNumber | integer | Required on create; 1 … `trip.dayCount` |
| destinationName | string | Required, 1–100 chars, trimmed |
| time | string \| null | Optional; `HH:mm` 24-hour |
| cost | number \| null | Optional; ≥ 0, max 2 decimals, ≤ 10,000,000 |
| priority | enum \| null | Optional; `high` \| `medium` \| `low` |

## 4. Endpoints Summary
| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/health` | Health check | No |
| POST | `/auth/signup` | Create account and log in | No |
| POST | `/auth/login` | Log in | No |
| POST | `/auth/logout` | Log out (clear cookie) | No |
| GET | `/auth/me` | Current user | Yes |
| DELETE | `/auth/me` | Delete my account and all my data | Yes |
| GET | `/trips` | List my trips | Yes |
| POST | `/trips` | Create trip (with "Draft 1") | Yes |
| GET | `/trips/{tripId}` | Get trip with draft summaries | Yes |
| PATCH | `/trips/{tripId}` | Edit trip details | Yes |
| DELETE | `/trips/{tripId}` | Delete trip and everything in it | Yes |
| POST | `/trips/{tripId}/finalize` | Finalize trip from a draft | Yes |
| POST | `/trips/{tripId}/reopen` | Move finalized trip back to draft | Yes |
| GET | `/trips/{tripId}/export.pdf` | Download itinerary PDF (finalized only) | Yes |
| GET | `/trips/{tripId}/drafts` | List draft summaries | Yes |
| POST | `/trips/{tripId}/drafts` | Create draft (blank or copy) | Yes |
| GET | `/drafts/{draftId}` | Get full draft with days and activities | Yes |
| PATCH | `/drafts/{draftId}` | Rename draft | Yes |
| DELETE | `/drafts/{draftId}` | Delete draft | Yes |
| POST | `/drafts/{draftId}/activities` | Add activity | Yes |
| PATCH | `/activities/{activityId}` | Edit / move activity | Yes |
| DELETE | `/activities/{activityId}` | Delete activity | Yes |

## 5. Endpoint Details

### `GET /health`
- **Auth required:** No
- **Success — `200`:** `{ "status": "ok" }`
- **Database unreachable — `503`:** `{ "status": "degraded" }`

---

### `POST /auth/signup`
- **Description:** Creates a user, sets the `gy_session` cookie (user is logged in).
- **Auth required:** No

**Request body**
```json
{ "username": "riya_travels", "password": "s3cure-pass" }
```
Rules: `username` 3–30 chars, letters/numbers/underscore, unique (case-insensitive); `password` 8–128 chars.

**Success response — `201`** (+ `Set-Cookie: gy_session=…`)
```json
{ "user": { "id": "6f1c...", "username": "riya_travels", "createdAt": "2026-10-03T10:15:00Z" } }
```

**Error responses**
| Status | Code | Condition |
|--------|------|-----------|
| 400 | VALIDATION_ERROR | Invalid username/password format |
| 409 | USERNAME_TAKEN | Username already exists |
| 429 | RATE_LIMITED | Too many attempts |

---

### `POST /auth/login`
- **Auth required:** No

**Request body**
```json
{ "username": "riya_travels", "password": "s3cure-pass" }
```

**Success response — `200`** (+ `Set-Cookie: gy_session=…`)
```json
{ "user": { "id": "6f1c...", "username": "riya_travels", "createdAt": "2026-10-03T10:15:00Z" } }
```

**Error responses**
| Status | Code | Condition |
|--------|------|-----------|
| 400 | VALIDATION_ERROR | Missing fields |
| 401 | INVALID_CREDENTIALS | Wrong username or password (same message for both) |
| 429 | RATE_LIMITED | Too many attempts |

---

### `POST /auth/logout`
- **Auth required:** No (always succeeds)
- **Success — `204`:** No body; `Set-Cookie` clears `gy_session`.

---

### `GET /auth/me`
- **Auth required:** Yes
- **Success — `200`:** `{ "user": User }`
- **Errors:** `401 UNAUTHORIZED`

---

### `DELETE /auth/me`
- **Description:** Permanently deletes the current user's account and **all** their trips, drafts and activities, then clears the session cookie. Cannot be undone.
- **Auth required:** Yes

**Request body**
```json
{ "password": "s3cure-pass" }
```

**Success response — `204`** (+ `Set-Cookie` clears `gy_session`). No body.

**Error responses**
| Status | Code | Condition |
|--------|------|-----------|
| 400 | VALIDATION_ERROR | Missing password |
| 401 | UNAUTHORIZED | Not logged in |
| 401 | INVALID_CREDENTIALS | Password is wrong |
| 429 | RATE_LIMITED | Too many attempts |

---

### `GET /trips`
- **Description:** All trips of the current user, newest `updatedAt` first.
- **Auth required:** Yes
- **Query params:** `status` (optional): `draft` | `finalized`

**Success response — `200`**
```json
{ "trips": [ Trip, Trip ] }
```

**Error responses:** `400 VALIDATION_ERROR` (bad `status`), `401 UNAUTHORIZED`

---

### `POST /trips`
- **Description:** Creates a trip in `draft` status with one empty draft named "Draft 1".
- **Auth required:** Yes

**Request body**
```json
{ "destination": "Goa", "startDate": "2026-11-14", "endDate": "2026-11-17", "tripType": "friends" }
```

**Success response — `201`**
```json
{ "trip": TripDetail }
```

**Error responses**
| Status | Code | Condition |
|--------|------|-----------|
| 400 | VALIDATION_ERROR | Missing/invalid fields, end before start, length > 30 days |
| 401 | UNAUTHORIZED | Not logged in |

---

### `GET /trips/{tripId}`
- **Auth required:** Yes
- **Success — `200`:** `{ "trip": TripDetail }`
- **Errors:** `401 UNAUTHORIZED`, `404 NOT_FOUND`

---

### `PATCH /trips/{tripId}`
- **Description:** Edit trip details. All fields optional. Changing dates re-maps days: activities keep their `dayNumber`; if the new `dayCount` is smaller, activities on days > new `dayCount` (in **all** drafts) are deleted — only when `confirmDeleteActivities` is `true`.
- **Auth required:** Yes

**Request body**
```json
{ "destination": "North Goa", "startDate": "2026-11-14", "endDate": "2026-11-15", "tripType": "friends", "confirmDeleteActivities": false }
```

**Success response — `200`**
```json
{ "trip": TripDetail, "deletedActivityCount": 0 }
```

**Error responses**
| Status | Code | Condition |
|--------|------|-----------|
| 400 | VALIDATION_ERROR | Invalid fields / date range |
| 404 | NOT_FOUND | Trip not found |
| 409 | TRIP_FINALIZED | Trip is finalized |
| 409 | ACTIVITIES_WOULD_BE_DELETED | Shortening would delete activities and `confirmDeleteActivities` is not `true` |

`ACTIVITIES_WOULD_BE_DELETED` details (frontend shows these in the warning, then resends with `confirmDeleteActivities: true`):
```json
{
  "error": {
    "code": "ACTIVITIES_WOULD_BE_DELETED",
    "message": "Shortening this trip will delete 3 activities.",
    "details": {
      "affected": [
        { "draftId": "d1...", "draftName": "Draft 1", "dayNumber": 3, "activityId": "a7...", "destinationName": "Dudhsagar Falls" }
      ]
    }
  }
}
```

---

### `DELETE /trips/{tripId}`
- **Description:** Deletes the trip, all its drafts and activities. Allowed for draft and finalized trips.
- **Auth required:** Yes
- **Success — `204`:** No body
- **Errors:** `401 UNAUTHORIZED`, `404 NOT_FOUND`

---

### `POST /trips/{tripId}/finalize`
- **Description:** Marks the trip `finalized` using the given draft. The trip and all its drafts become read-only; other drafts are kept.
- **Auth required:** Yes

**Request body**
```json
{ "draftId": "d1..." }
```

**Success response — `200`**
```json
{ "trip": TripDetail }
```
(`status: "finalized"`, `finalizedDraftId: "d1..."`, that draft has `isFinal: true`.)

**Error responses**
| Status | Code | Condition |
|--------|------|-----------|
| 400 | VALIDATION_ERROR | Missing `draftId` or draft does not belong to this trip |
| 404 | NOT_FOUND | Trip not found |
| 409 | TRIP_FINALIZED | Trip already finalized |

---

### `POST /trips/{tripId}/reopen`
- **Description:** Moves a finalized trip back to `draft`; everything is editable again. `finalizedDraftId` becomes `null`.
- **Auth required:** Yes
- **Request body:** none (`{}` allowed)
- **Success — `200`:** `{ "trip": TripDetail }`

**Error responses**
| Status | Code | Condition |
|--------|------|-----------|
| 404 | NOT_FOUND | Trip not found |
| 409 | TRIP_NOT_FINALIZED | Trip is already a draft |

---

### `GET /trips/{tripId}/export.pdf`
- **Description:** Generates the itinerary PDF from the finalized draft: trip details, each day with its activities (time, destination name, cost, priority label), day totals, and the trip total in INR, with the GhumakkadYatri logo.
- **Auth required:** Yes

**Success response — `200`**
- `Content-Type: application/pdf`
- `Content-Disposition: attachment; filename="GhumakkadYatri-Goa-2026-11-14.pdf"` (destination with non-alphanumeric characters replaced by `-`)
- Body: PDF bytes

**Error responses** (JSON error body)
| Status | Code | Condition |
|--------|------|-----------|
| 401 | UNAUTHORIZED | Not logged in |
| 404 | NOT_FOUND | Trip not found |
| 409 | TRIP_NOT_FINALIZED | Trip is a draft |

---

### `GET /trips/{tripId}/drafts`
- **Auth required:** Yes
- **Success — `200`:** `{ "drafts": [ DraftSummary ] }` (oldest first)
- **Errors:** `401 UNAUTHORIZED`, `404 NOT_FOUND`

---

### `POST /trips/{tripId}/drafts`
- **Description:** Creates a new draft — blank, or a copy of an existing draft (all its activities are copied).
- **Auth required:** Yes

**Request body**
```json
{ "name": "Hills plan", "copyFromDraftId": "d1..." }
```
`copyFromDraftId` is optional (`null`/omitted = blank draft) and must belong to the same trip.

**Success response — `201`**
```json
{ "draft": Draft }
```

**Error responses**
| Status | Code | Condition |
|--------|------|-----------|
| 400 | VALIDATION_ERROR | Invalid name or `copyFromDraftId` |
| 404 | NOT_FOUND | Trip not found |
| 409 | TRIP_FINALIZED | Trip is finalized |
| 409 | DRAFT_NAME_TAKEN | Name already used in this trip |
| 409 | DRAFT_LIMIT_REACHED | Trip already has 5 drafts |

---

### `GET /drafts/{draftId}`
- **Auth required:** Yes
- **Success — `200`:** `{ "draft": Draft }`
- **Errors:** `401 UNAUTHORIZED`, `404 NOT_FOUND`

The Compare Drafts page calls this twice (one per draft); there is no separate compare endpoint.

---

### `PATCH /drafts/{draftId}`
- **Description:** Rename a draft.
- **Auth required:** Yes

**Request body**
```json
{ "name": "Beach plan" }
```

**Success — `200`:** `{ "draft": DraftSummary }`

**Error responses:** `400 VALIDATION_ERROR`, `404 NOT_FOUND`, `409 TRIP_FINALIZED`, `409 DRAFT_NAME_TAKEN`

---

### `DELETE /drafts/{draftId}`
- **Auth required:** Yes
- **Success — `204`:** No body

**Error responses:** `404 NOT_FOUND`, `409 TRIP_FINALIZED`, `409 LAST_DRAFT`

---

### `POST /drafts/{draftId}/activities`
- **Auth required:** Yes

**Request body**
```json
{ "dayNumber": 1, "destinationName": "Baga Beach", "time": "09:30", "cost": 0, "priority": "high" }
```
`time`, `cost`, `priority` optional (omit or `null`).

**Success response — `201`**
```json
{ "activity": Activity }
```

**Error responses**
| Status | Code | Condition |
|--------|------|-----------|
| 400 | VALIDATION_ERROR | Invalid fields or `dayNumber` outside 1…`dayCount` |
| 404 | NOT_FOUND | Draft not found |
| 409 | TRIP_FINALIZED | Trip is finalized |

---

### `PATCH /activities/{activityId}`
- **Description:** Edit any field; changing `dayNumber` moves the activity to another day in the same draft.
- **Auth required:** Yes

**Request body** (all optional)
```json
{ "dayNumber": 2, "destinationName": "Baga Beach", "time": null, "cost": 150, "priority": "low" }
```

**Success — `200`:** `{ "activity": Activity }`

**Error responses:** `400 VALIDATION_ERROR`, `404 NOT_FOUND`, `409 TRIP_FINALIZED`

---

### `DELETE /activities/{activityId}`
- **Auth required:** Yes
- **Success — `204`:** No body
- **Errors:** `404 NOT_FOUND`, `409 TRIP_FINALIZED`

## 6. Change Log
| Date | Change | Author |
|------|--------|--------|
| 2026-10-03 | Initial contract: auth, trips, drafts, activities, finalize/reopen, PDF export | Priyanka Ghate (with Claude) |
| 2026-10-03 | `/health` returns `503 degraded` when the database is unreachable (from backend spec) | Priyanka Ghate (with Claude) |
| 2026-10-03 | Added `DELETE /auth/me` (delete account, MVP); rate limit also covers it | Priyanka Ghate (with Claude) |
