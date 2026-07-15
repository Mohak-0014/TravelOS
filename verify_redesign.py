"""
Screenshot every TravelOS frontend route for visual verification during the
"Quiet Atlas" redesign. Logs in with a fresh throwaway account each run (the
hardcoded JWTs in verify_ui.py / verify_trip.py expire), creates one real trip
via the API, and mocks the `generating` / `awaiting_approval` trip states via
Playwright route interception so those screens don't require actually running
the multi-agent graph.

Usage:
    py verify_redesign.py --label p2               # screenshots/p2/*.png
    py verify_redesign.py --label p2 --mobile-only
    py verify_redesign.py --label p2 --reduced-motion
"""

import argparse
import asyncio
import json
import sys
import time
import urllib.error
import urllib.request
from functools import partial
from pathlib import Path

from playwright.async_api import async_playwright, ConsoleMessage

API_BASE = "http://localhost:8000"
WEB_BASE = "http://localhost:3000"
DESKTOP = {"width": 1400, "height": 900}
MOBILE = {"width": 390, "height": 844}


def api_request(method: str, path: str, body: dict | None = None, token: str | None = None) -> dict:
    req = urllib.request.Request(
        f"{API_BASE}{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Content-Type": "application/json",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        print(f"  ! {method} {path} -> {e.code}: {e.read().decode()[:300]}")
        raise


def bootstrap_account() -> dict:
    """Registers a fresh throwaway user, logs in, creates one trip + share link."""
    email = f"verify_redesign_{int(time.time())}@travelos.dev"
    password = "verify-redesign-pw-1!"

    print(f"=== Bootstrapping {email} ===")
    api_request(
        "POST",
        "/api/v1/auth/register",
        {
            "email": email,
            "password": password,
            "full_name": "Redesign Verifier",
        },
    )
    token_data = api_request("POST", "/api/v1/auth/login", {"email": email, "password": password})
    token = token_data["access_token"]

    api_request(
        "PUT",
        "/api/v1/preferences",
        {
            "pace": "moderate",
            "luxury_tier": "mid",
            "walking_tolerance": "moderate",
            "food_prefs": ["local", "street_food"],
            "interests": ["culture", "food"],
            "budget_behavior": "balanced",
        },
        token=token,
    )

    trip = api_request(
        "POST",
        "/api/v1/trips",
        {
            "title": "Tokyo Trip",
            "destination_city": "Tokyo",
            "destination_country": "Japan",
            "start_date": "2026-09-01",
            "end_date": "2026-09-07",
            "num_travelers": 2,
            "budget_total": 3000,
            "budget_currency": "USD",
            "flight_origin": "JFK",
        },
        token=token,
    )

    shared = api_request("POST", f"/api/v1/trips/{trip['id']}/share", token=token)

    print(f"  user={email} trip={trip['id']} share_token={shared.get('share_token')}")
    return {"email": email, "token": token, "trip": trip, "share_token": shared.get("share_token")}


# ── Mocked trip payloads for states that need a running agent graph ──────────


def generating_trip(base: dict) -> dict:
    return {**base, "status": "generating"}


def awaiting_approval_trip(base: dict) -> dict:
    return {
        **base,
        "status": "awaiting_approval",
        "budget_state": {
            "by_category": {"lodging": 900, "activity": 400, "meal": 500, "transport": 150},
            "total_planned": 1950,
            "budget_total": 3000,
            "deviation_pct": -35,
            "currency": "USD",
        },
    }


MOCK_APPROVALS = [
    {
        "id": "11111111-1111-1111-1111-111111111111",
        "trip_id": "TRIP_ID",
        "proposed_by": "weather_agent",
        "change_type": "concierge_swap",
        "summary": "Rain expected — swapping the outdoor walking tour for an indoor option.",
        "payload": {
            "day": 3,
            "current": {
                "title": "Yanaka Walking Tour",
                "item_type": "activity",
                "start_time": "10:00:00",
                "est_cost": 0,
            },
            "alternatives": [
                {
                    "title": "teamLab Planets",
                    "description": "Immersive digital art museum, fully indoor.",
                },
                {
                    "title": "Nezu Museum",
                    "description": "Japanese & East Asian art, quiet garden cafe.",
                },
            ],
            "reason": "70% chance of rain on Day 3 — the walking tour would be miserable.",
        },
        "status": "pending",
        "created_at": "2026-08-20T09:00:00Z",
        "resolved_at": None,
    },
    {
        "id": "22222222-2222-2222-2222-222222222222",
        "trip_id": "TRIP_ID",
        "proposed_by": "budget_agent",
        "change_type": "budget_upgrade",
        "summary": "You're under budget — consider upgrading dinner on Day 5.",
        "payload": {
            "title": "Omakase at Sushi Saito",
            "description": "One of Tokyo's top sushi counters.",
            "reason": "You're tracking 35% under budget with 2 days left to allocate.",
            "budget_remaining": 1050,
            "currency": "USD",
        },
        "status": "pending",
        "created_at": "2026-08-20T09:05:00Z",
        "resolved_at": None,
    },
    {
        "id": "33333333-3333-3333-3333-333333333333",
        "trip_id": "TRIP_ID",
        "proposed_by": "events_agent",
        "change_type": "event_add",
        "summary": "A festival was found near your Day 4 itinerary.",
        "payload": {
            "source": "ticketmaster",
            "category": "Music",
            "event_name": "Summer Sonic Satellite",
            "day_number": 4,
            "venue_name": "Makuhari Messe",
            "start_time": "18:00",
            "price_min": 80,
            "price_max": 150,
            "url": "https://example.com/event",
        },
        "status": "pending",
        "created_at": "2026-08-20T09:10:00Z",
        "resolved_at": None,
    },
]


async def install_state_mocks(context, trip_id: str, base_trip: dict, state: str):
    """Intercepts GET /trips/{id} (and /approvals for awaiting_approval) to force a render state."""
    if state == "generating":
        payload = generating_trip(base_trip)
    elif state == "awaiting_approval":
        payload = awaiting_approval_trip(base_trip)
    else:
        return

    async def handle_trip(route):
        await route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))

    await context.route(f"{API_BASE}/api/v1/trips/{trip_id}", handle_trip)

    if state == "awaiting_approval":
        approvals = [{**a, "trip_id": trip_id} for a in MOCK_APPROVALS]

        async def handle_approvals(route):
            await route.fulfill(
                status=200, content_type="application/json", body=json.dumps(approvals)
            )

        await context.route(f"{API_BASE}/api/v1/trips/{trip_id}/approvals*", handle_approvals)


async def shoot(
    page,
    path: str,
    out: Path,
    name: str,
    wait_ms: int = 1500,
    full_page: bool = True,
    only: list[str] | None = None,
):
    if only and not any(s in name for s in only):
        print(f"  (skip {name}, --only filter)")
        return
    # NOTE: full_page=True screenshots of routes with a <Globe> (cobe/WebGL
    # canvas) can render mostly blank — Chromium's full-page capture resizes
    # the viewport to the full scrollHeight before compositing, which can
    # disrupt an active WebGL canvas and the surrounding paint. This is a
    # screenshot-tooling artifact, not a real bug: scrolling normally (a
    # plain viewport screenshot at each scroll position) renders everything
    # correctly. If a full-page shot of "/" or "/trips" looks blank, re-check
    # with a viewport-only (full_page=False) pass before assuming a regression.
    # "load" not "networkidle": Next dev mode keeps the webpack-HMR websocket
    # open forever, so networkidle would never resolve. Timeout is generous:
    # this environment's dev-mode cold compiles are severely I/O-throttled
    # (OneDrive sync + likely Defender scanning .next) — observed up to ~280s
    # for a single small route on first visit. Once a route is warm in a
    # given dev-server process it stays fast; avoid restarting the server.
    await page.goto(f"{WEB_BASE}{path}", wait_until="load", timeout=300000)
    await page.wait_for_timeout(wait_ms)
    if full_page:
        # whileInView reveals only fire once a section crosses the real viewport;
        # a full-page screenshot captures below-the-fold DOM that a plain load
        # never scrolled past, which would otherwise strand those sections at
        # their initial (opacity: 0) state. Walk down (and back up) first so
        # every section actually triggers, matching what a scrolling user sees.
        height = await page.evaluate("document.body.scrollHeight")
        viewport_h = page.viewport_size["height"]
        for y in range(0, height, viewport_h // 2):
            await page.evaluate(f"window.scrollTo(0, {y})")
            await page.wait_for_timeout(120)
        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(300)
    await page.screenshot(path=str(out / f"{name}.png"), full_page=full_page)
    print(f"  [{page.viewport_size['width']}x{page.viewport_size['height']}] {path} -> {name}.png")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="baseline", help="subfolder under screenshots/")
    parser.add_argument("--mobile-only", action="store_true")
    parser.add_argument("--desktop-only", action="store_true")
    parser.add_argument("--reduced-motion", action="store_true")
    parser.add_argument(
        "--only",
        default=None,
        help="comma-separated substrings to filter which named screenshots run (keeps re-checks of one page fast)",
    )
    args = parser.parse_args()
    only = [s.strip() for s in args.only.split(",")] if args.only else None

    out_dir = Path(__file__).parent / "screenshots" / args.label
    out_dir.mkdir(parents=True, exist_ok=True)

    account = bootstrap_account()
    trip = account["trip"]
    store = json.dumps(
        {
            "state": {
                "token": account["token"],
                "user": {"email": account["email"]},
                "_hasHydrated": True,
            },
            "version": 0,
        }
    )

    console_errors: list[str] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        viewports = []
        if not args.mobile_only:
            viewports.append(("desktop", DESKTOP))
        if not args.desktop_only:
            viewports.append(("mobile", MOBILE))

        for tag, viewport in viewports:
            print(f"\n--- {tag} ({viewport['width']}x{viewport['height']}) ---")
            ctx_kwargs = {"viewport": viewport}
            if args.reduced_motion:
                ctx_kwargs["reduced_motion"] = "reduce"
            ctx = await browser.new_context(**ctx_kwargs)
            await ctx.add_init_script(f"localStorage.setItem('auth-store', {json.dumps(store)});")

            def on_console(msg: ConsoleMessage, _tag=tag):
                if msg.type == "error":
                    console_errors.append(f"[{_tag}] {msg.text}")

            page = await ctx.new_page()
            page.on("console", on_console)
            sub = out_dir / tag
            sub.mkdir(exist_ok=True)
            shoot_ = partial(shoot, only=only)

            # Public / unauthenticated
            logged_out = await browser.new_context(viewport=viewport)
            lo_page = await logged_out.new_page()
            lo_page.on("console", on_console)
            await shoot_(lo_page, "/", sub, "01-landing")
            await shoot_(lo_page, "/login", sub, "02-login")
            await logged_out.close()

            # Authenticated flows
            await shoot_(page, "/trips", sub, "03-trips-dashboard")
            await shoot_(page, "/trips/new", sub, "04-trip-wizard-step1")
            await shoot_(page, "/onboarding", sub, "05-onboarding")
            await shoot_(page, "/profile", sub, "06-profile")
            await shoot_(page, f"/trips/{trip['id']}", sub, "07-trip-detail-planning")

            # Mocked render states
            await install_state_mocks(ctx, trip["id"], trip, "generating")
            await shoot_(page, f"/trips/{trip['id']}", sub, "08-trip-detail-generating")

            await install_state_mocks(ctx, trip["id"], trip, "awaiting_approval")
            await shoot_(page, f"/trips/{trip['id']}", sub, "09-trip-detail-awaiting-approval")
            await ctx.unroute(f"{API_BASE}/api/v1/trips/{trip['id']}")

            # Share page (separate logged-out context — share is public)
            if account["share_token"]:
                share_ctx = await browser.new_context(viewport=viewport)
                share_page = await share_ctx.new_page()
                share_page.on("console", on_console)
                await shoot_(share_page, f"/share/{account['share_token']}", sub, "10-share")
                await share_ctx.close()

            await ctx.close()

        await browser.close()

    print(f"\n=== Screenshots written to {out_dir} ===")
    if console_errors:
        print(f"\n!!! {len(console_errors)} console error(s):")
        for e in console_errors[:30]:
            print(f"  {e}")
        sys.exit(1)
    else:
        print("No console errors.")


if __name__ == "__main__":
    asyncio.run(main())
