# Goal Spec — Trip Planner

> Purpose: Define *why* we are building this and *what success looks like*. All other specs must trace back to this document.

## 1. Product Overview
- **Product name:** GhumakkadYatri
- **One-line pitch:** A one-stop web app where any traveller — solo, couple, family, or group of friends — plans a trip day by day and exports a clean itinerary.
- **Problem statement:** Travellers planning a trip typically scatter their day-by-day plans across notes apps, spreadsheets, and chat threads. This makes the itinerary hard to keep organized, hard to share, and hard to reference while travelling. GhumakkadYatri gives travellers a single place to plan a trip day by day, access it from any device, and export a clean itinerary.

## 2. Target Users / Personas
| Persona | Description | Primary needs |
|---------|-------------|---------------|
| Solo traveller | Individual planning a personal trip | Quick trip setup; a simple day-by-day plan they can check on their phone while travelling |
| Couple | Two people planning a leisure trip or holiday | A shared, organized plan within fixed dates; an exportable itinerary |
| Family | Parents/children or extended family travelling together | A structured daily schedule that fits the trip dates; a printable (PDF) itinerary |
| Group of friends | Friends travelling together within or across countries | One place for the plan instead of scattered chat threads; an itinerary to share with the group |

## 3. Goals
<!-- Measurable outcomes. -->
- **G1 — Single planning place:** A signed-in user can go from a new trip to a complete day-by-day itinerary inside the app, with no external notes or spreadsheets needed.
- **G2 — Access from any device:** Trips are stored on the server against the user's account. Logging in from any device (laptop or mobile browser) shows the same, up-to-date trips.
- **G3 — Shareable output:** Any trip can be exported as a clean, readable PDF itinerary.
- **G4 — Ship fast:** A working MVP (all P0 user stories) is delivered within 2 weeks by 1 developer.

## 4. Non-Goals (Out of Scope)
- **NG1:** Booking or payment of any kind: flights, hotels, transport, or local activities/attractions. The app plans trips; it does not book them.
- **NG2:** Native mobile apps (iOS/Android). Mobile users use the responsive web app.
- **NG3:** Real-time collaborative editing of one trip by multiple users (MVP trips belong to a single user).
- **NG4:** General-purpose chat or Q&A. The app is limited to trip planning.
- **NG5:** Corporate / business travel. The app is for personal and leisure travel only (solo, couple, family, friends).

## 5. Core User Stories
<!-- Format: As a <persona>, I want <capability> so that <benefit>. -->
| ID | User story | Priority (P0/P1/P2) | Goal |
|----|------------|---------------------|------|
| US-1 | As a new traveller, I want to sign up with a username and password so that my trips are saved to my own account. | P0 | G1, G2 |
| US-2 | As a returning traveller, I want to log in from any device so that I can see and continue my trips wherever I am. | P0 | G2 |
| US-3 | As a traveller, I want to log out so that others using the same device cannot see my trips. | P0 | G2 |
| US-4 | As a traveller, I want to create a trip with a destination, start date, end date, and trip type (solo, couple, family, friends) so that the app can set up the plan for my trip. New trips start as **Draft**. | P0 | G1 |
| US-5 | As a traveller, I want to see a list of all my trips so that I can quickly open the one I need. | P0 | G1, G2 |
| US-6 | As a traveller, I want my trip plan to be automatically divided into Day 1 to Day N based on my trip dates so that I don't have to set up each day by hand. | P0 | G1 |
| US-7 | As a traveller, I want to add, edit, and remove activities for each day — each with a destination name, time, and cost — so that my itinerary shows where I'm going, when, and how much it will cost. | P0 | G1 |
| US-7a | As a traveller, I want to set a priority (High / Medium / Low) for each activity so that I know which activities matter most if time or budget runs short. | P1 | G1 |
| US-8 | As a traveller, I want to mark my trip as **Finalized** when I'm done planning so that it is clear which plan is ready to use. | P0 | G3 |
| US-8a | As a traveller, I want to keep multiple draft versions of the same trip (e.g. "Beach plan" vs "Hills plan") so that I can try different plans before choosing one. | P1 | G1 |
| US-8b | As a traveller, I want to compare two drafts of a trip side by side (day-by-day activities and total cost) so that I can pick the better plan to finalize. | P2 | G1 |
| US-9 | As a traveller, I want to export a Finalized trip's itinerary as a PDF so that I can print it, share it, or view it offline. | P0 | G3 |
| US-9a | As a traveller, I want to reopen a Finalized trip for editing so that I can change my plan when things change, then finalize and export it again. | P0 | G1, G3 |
| US-10 | As a traveller, I want to edit a trip's details (destination, dates, type) so that I can fix mistakes or adjust plans. | P1 | G1 |
| US-11 | As a traveller, I want to delete a trip I no longer need so that my trip list stays clean. | P1 | G1 |
| US-12 | As a traveller on my phone, I want the app to work well on a mobile browser so that I can check my plan while travelling. | P1 | G2 |

## 6. Key Features (MVP)
- [ ] **F1 — Authentication:** Users can sign up (username + password), log in, and log out through login/signup screens. *(US-1, US-2, US-3)*
- [ ] **F2 — Create trip:** Users can create a trip with destination, start date, end date, and trip type (solo, couple, family, friends). *(US-4)*
- [ ] **F3 — Trip list:** Users can view a list of the trips they have created, showing each trip's status (Draft / Finalized). *(US-5)*
- [ ] **F4 — Day-by-day planner:** Users can open a trip and add, edit, or remove activities for each day from Day 1 to Day N (N derived from start/end dates). Each activity has:
  - **Destination name** (the place to visit) — required
  - **Time** — optional; a single start time (e.g. 10:00)
  - **Cost** — optional; in one fixed currency, **INR (₹)**
  - **Priority** — optional; High / Medium / Low, chosen by the user (P1, see F8)

  Activities within a day are listed in order of start time; activities without a time appear at the end of that day. *(US-6, US-7)*
- [ ] **F5 — Finalize & PDF export:** Every trip has a status: **Draft** (while planning, fully editable) or **Finalized** (planning complete). Users can mark a Draft trip as Finalized. Only Finalized trips can be exported as a PDF; the export option is not available for Draft trips. A Finalized trip is read-only; the user can **Reopen for editing**, which moves it back to Draft, then finalize it again before exporting. *(US-8, US-9, US-9a)*
- [ ] **F6 — Manage trips (P1):** Users can edit trip details and delete trips. *(US-10, US-11)*
- [ ] **F7 — Responsive UI (P1):** All screens are usable on laptop and mobile browsers. *(US-12)*
- [ ] **F8 — Activity priority (P1):** Users can set a priority (High / Medium / Low) on each activity. Priority is a label only, shown in the planner and in the PDF; it does not change the order (activities stay sorted by time). *(US-7a)*
- [ ] **F9 — Multiple drafts (P1):** A trip can have several named draft versions of its plan. The user can create a new draft (blank or copied from an existing one), rename, and delete drafts. Finalizing one draft makes it the trip's Finalized plan; Reopen for editing returns it to Draft. *(US-8a)*
- [ ] **F10 — Compare drafts (P2):** The user selects two drafts and sees them side by side: activities per day and total cost per day and per trip. *(US-8b)*

## 7. Future Features (Post-MVP)
- **Budget-fit suggestions:** The app suggests how to fit the trip within a given budget.
- **Repeat-trip suggestions:** Based on a user's past trips, the app suggests reusing or adapting earlier plans for a new trip.
- **Import travel data:** Users can upload Excel, Word, or other files with travel information (bookings, notes) to pre-fill a trip plan.
- **Trip sharing / collaboration:** Invite companions to view or co-edit a trip.
- **AI travel assistant:** Destination and activity suggestions, restricted to travel topics (see Risks).

## 8. Success Metrics / Acceptance Criteria
| Metric | Target |
|--------|--------|
| A user can sign up, log in, and log out | 100% of attempts with valid input succeed; invalid credentials show a clear error |
| A user can create a trip | Trip is saved and appears in the trip list immediately |
| A user can see their trips on another device | Trips created on device A appear after logging in on device B |
| A user can plan day-by-day activities | Plan shows exactly N days for an N-day trip; activities persist after page reload |
| A user can finalize a trip | Trip status changes from Draft to Finalized and is shown in the trip list |
| A user can export a Finalized trip as PDF | PDF downloads and contains trip details and every day's activities in order |
| Draft trips cannot be exported | Export is hidden/disabled in the UI and rejected by the API for Draft trips |
| A user can reopen a Finalized trip | Status changes back to Draft and the plan becomes editable again; editing a Finalized trip without reopening is rejected |
| PDF shows costs | Each activity's cost and a total cost per day and per trip are shown in INR |
| A user cannot see another user's trips | Accessing another user's trip is denied (verified by test) |
| MVP delivery | All P0 user stories done within 2 weeks |

## 9. Constraints & Assumptions
- **Tech constraints:** Responsive web application that works on common laptop and mobile browsers (latest Chrome, Edge, Safari, Firefox).
- **Timeline:** 2 weeks for the MVP.
- **Team:** 1 developer.
- **Budget / third-party services:** Prefer free/open-source tools and free hosting tiers; no paid third-party APIs in MVP.
- **Assumptions:**
  - After launch, updates are released about once every 2 months.
  - Each trip belongs to one user; no sharing in MVP.
  - Trips are between 1 and 30 days long.

## 10. Risks & Open Questions
- [ ] **Data privacy:** User login data must be protected (hashed passwords, HTTPS, no plain-text secrets). What else is required, e.g. account deletion, data retention?
- [ ] **Off-topic use:** If an AI assistant is added later, how do we keep users from asking non-travel questions? *(Not applicable to MVP, which has no chat.)*
- [x] **"Finalized" trips:** **Resolved:** trips are Draft while planning; only Finalized trips can be exported to PDF.
  - [x] Follow-up: **Resolved:** Finalized trips are read-only; "Reopen for editing" moves them back to Draft.
- [x] **Activity details:** ~~What fields does an activity have?~~ **Resolved:** destination name, time, cost.
  - [x] Follow-up: **Resolved:** destination name required; time and cost optional.
  - [x] Follow-up: **Resolved:** time is a single start time.
  - [x] Follow-up: **Resolved:** one fixed currency, INR.
  - [x] Follow-up: **Resolved:** users can set a priority (High / Medium / Low) per activity (F8, P1); label only, order stays by time.
- [x] **Multiple drafts:** **Resolved:** a trip can have multiple drafts (F9, P1) that can be compared side by side (F10, P2); Reopen for editing is kept.
- [ ] **Timeline risk:** 2 weeks with 1 developer is tight; P1 items may slip to post-MVP.
