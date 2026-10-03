"""End-to-end smoke test against a running deployment (implementation plan task 6.5).

Usage:  python scripts/smoke_test.py https://<your-app>.vercel.app
Signs up a throwaway user, plans and finalizes a trip, downloads the PDF, then deletes the account.
Standard library only, so it runs without the project's virtual environment.
"""

import json
import secrets
import sys
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from typing import Any

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/") + "/api/v1"
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))


def call(method: str, path: str, body: dict[str, Any] | None = None) -> tuple[int, bytes]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with opener.open(req, timeout=60) as res:
            return res.status, res.read()
    except urllib.error.HTTPError as err:
        return err.code, err.read()


def step(name: str, method: str, path: str, expect: int, body: dict[str, Any] | None = None) -> Any:
    status, raw = call(method, path, body)
    ok = status == expect
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {status}")
    if not ok:
        print(raw.decode(errors="replace")[:500])
        sys.exit(1)
    return raw if path.endswith(".pdf") else (json.loads(raw) if raw else None)


user = {"username": f"smoke_{secrets.token_hex(4)}", "password": secrets.token_urlsafe(12)}
step("health", "GET", "/health", 200)
step("signup", "POST", "/auth/signup", 201, user)
trip = step(
    "create trip",
    "POST",
    "/trips",
    201,
    {
        "destination": "Goa",
        "startDate": "2026-11-14",
        "endDate": "2026-11-17",
        "tripType": "friends",
    },
)["trip"]
draft_id = trip["drafts"][0]["id"]
step(
    "add activity",
    "POST",
    f"/drafts/{draft_id}/activities",
    201,
    {"dayNumber": 1, "destinationName": "Baga Beach", "time": "09:30", "cost": 1250.5},
)
step("export blocked for draft", "GET", f"/trips/{trip['id']}/export.pdf", 409)
step("finalize", "POST", f"/trips/{trip['id']}/finalize", 200, {"draftId": draft_id})
pdf = step("export pdf", "GET", f"/trips/{trip['id']}/export.pdf", 200)
print(f"      PDF size: {len(pdf)} bytes, starts with %PDF: {pdf.startswith(b'%PDF')}")
step("reopen", "POST", f"/trips/{trip['id']}/reopen", 200)
step("delete account", "DELETE", "/auth/me", 204, {"password": user["password"]})
step("logged out after delete", "GET", "/auth/me", 401)
print("All smoke tests passed.")
