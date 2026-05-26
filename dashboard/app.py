import os
from datetime import datetime, timedelta
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

app = FastAPI(title="TCG Arbitrage Dashboard")

BASE_DIR = os.path.dirname(__file__)
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

SCAN_INTERVAL_HOURS = int(os.getenv("SCAN_INTERVAL_HOURS", "8"))


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    from core.database import get_last_scans, get_recent_opportunities, get_watchlist

    all_opps = get_recent_opportunities(limit=200)
    watchlist = get_watchlist()
    last_scans = get_last_scans(limit=5)

    today = datetime.now().date()
    today_opps = [o for o in all_opps if o.scanned_at.date() == today]
    recent_opps = all_opps[:20]

    stats: dict[str, Any] = {
        "today_count": len(today_opps),
        "best_profit": max((o.gross_profit for o in today_opps), default=0.0),
        "best_roi": max((o.roi_pct for o in today_opps), default=0.0),
        "watchlist_size": len(watchlist),
    }

    # Last / next scan times
    last_scan = None
    next_scan_str = "pending first scan"
    if last_scans:
        last_scan = last_scans[0]
        last_dt = datetime.fromisoformat(last_scan["scanned_at"])
        next_dt = last_dt + timedelta(hours=SCAN_INTERVAL_HOURS)
        now = datetime.now()
        if next_dt > now:
            diff = next_dt - now
            h, rem = divmod(int(diff.total_seconds()), 3600)
            m = rem // 60
            next_scan_str = f"in {h}h {m}m" if h else f"in {m}m"
        else:
            next_scan_str = "imminent"

    return templates.TemplateResponse("index.html", {
        "request": request,
        "opportunities": sorted(today_opps, key=lambda o: o.gross_profit, reverse=True),
        "recent": recent_opps,
        "stats": stats,
        "last_scan": last_scan,
        "next_scan_str": next_scan_str,
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "scan_interval_hours": SCAN_INTERVAL_HOURS,
    })


@app.get("/health")
async def health():
    return {"status": "ok", "ts": datetime.now().isoformat()}
