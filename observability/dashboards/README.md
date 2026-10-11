# Dashboard: "GhumakkadYatri — Overview"

Create in SigNoz: **Dashboards → New dashboard → Add panel**, using the **Query Builder**. Data source per panel as listed. (observability-spec.md §4)

| # | Panel | Data source | Query | Visualisation |
|---|-------|-------------|-------|---------------|
| 1 | Active users | Traces | Aggregate `Count Distinct` of `enduser.id`; filter `service.name = ghumakkadyatri-api`; interval 1 day | Time series / Value |
| 2 | Logins & sign-ups | Metrics | `gy.logins` and `gy.signups`, `Sum` of rate → increase per day | Bar |
| 3 | Page views by route | Metrics | `gy.page_views`, Sum, group by `route` | Bar / Table |
| 4 | Trips by destination type | Metrics | `gy.trips.created`, Sum, group by `destination_type` | Pie |
| 5 | Top destinations / countries | Metrics | `gy.trips.created`, Sum, group by `destination` (and `country`), order desc, limit 10 | Table |
| 6 | Trips by top priority | Metrics | `gy.trips.created`, Sum, group by `top_priority` | Pie |
| 7 | Plan my day usage | Metrics | `gy.plans.generated`, Sum, group by `top_priority`, `has_stay` | Stacked bar |
| 8 | API latency by route | Traces | `durationNano` P50/P95/P99; filter `kind = Server`; group by `http.route` | Time series |
| 9 | API errors | Traces | Count; filter `http.response.status_code >= 400` (or `hasError = true`); group by `http.route` | Time series |
| 10 | External API latency | Metrics | `gy.external.duration` P95, group by `service` (nominatim, wikipedia); plus Count with `outcome != ok` | Time series |
| 11 | Database query time | Traces | `durationNano` P95; filter `db.system = postgresql` | Time series |
| 12 | Suggestions & hotels | Metrics | `gy.suggestions.requested`, `gy.hotels.requested`, Sum, group by `destination_type` | Bar |

Tips
- Metric names may appear with dots replaced by underscores in some SigNoz views (e.g. `gy_trips_created`).
- Destination types come from OpenStreetMap: `country`, `state`, `city`, `town`, `village`, `other`, `unknown`.
- Built-in SigNoz pages (Services, Traces, Exceptions) already show request rate, latency and errors for `ghumakkadyatri-api` without any setup.
