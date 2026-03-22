"""
main.py — FastAPI backend for Jicho la Wananchi
Serves the dashboard HTML and a JSON API for all civic data.
"""

import os
import json
from datetime import datetime, date
from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.background import BackgroundScheduler

import database as db
from scraper import run_all_scrapers
from summariser import run_summarisation


# ── Startup & scheduler ────────────────────────────────────────────────────────

def full_pipeline():
    """Scrape → Summarise. Runs nightly."""
    print(f"\n{'='*50}")
    print(f"Pipeline run: {datetime.now().isoformat()}")
    print('='*50)
    run_all_scrapers()
    run_summarisation()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Init DB
    db.init_db()

    # Seed data on first run (if DB is empty)
    bills = db.get_bills(limit=1)
    if not bills:
        print("Empty DB — running initial pipeline...")
        full_pipeline()

    # Schedule nightly at 02:00 Nairobi time (EAT = UTC+3)
    scheduler = BackgroundScheduler(timezone="Africa/Nairobi")
    scheduler.add_job(full_pipeline, "cron", hour=2, minute=0)
    scheduler.start()
    print("✓ Scheduler started — pipeline runs nightly at 02:00 EAT")

    yield

    scheduler.shutdown()


app = FastAPI(
    title="Jicho la Wananchi API",
    description="Kenya civic tracker — bills, gazette, executive actions",
    lifespan=lifespan,
)

# Serve static files (the dashboard HTML)
static_dir = Path("static")
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory="jicho/static"), name="static")


# ── Helper ─────────────────────────────────────────────────────────────────────

ELECTION_DATE = date(2027, 8, 10)  # approximate — update when official date set

def days_to_election() -> int:
    return (ELECTION_DATE - date.today()).days


def parse_key_facts(raw: str | None) -> list:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [item.get("fact", item) if isinstance(item, dict) else item for item in data]
    except Exception:
        pass
    return []


# ── Dashboard route ────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve the main dashboard. Reads the HTML template and injects live data."""
    template_path = Path("jicho/templates/dashboard.html")
    if not template_path.exists():
        return HTMLResponse("<h1>Dashboard template not found</h1>", status_code=500)
    return HTMLResponse(template_path.read_text())


# ── API Routes ─────────────────────────────────────────────────────────────────

@app.get("/api/stats")
async def get_stats():
    """Summary statistics for the dashboard header."""
    bill_counts = db.count_bills()
    total_bills = sum(bill_counts.values())
    passed = bill_counts.get("passed", 0)
    scrape_times = db.get_last_scrape_times()

    return {
        "days_to_election": days_to_election(),
        "election_date": ELECTION_DATE.isoformat(),
        "bills": {
            "total": total_bills,
            "passed": passed,
            "committee": bill_counts.get("committee", 0),
            "second_reading": bill_counts.get("second-reading", 0),
            "first_reading": bill_counts.get("first-reading", 0),
            "withdrawn": bill_counts.get("withdrawn", 0),
        },
        "last_updated": scrape_times,
        "generated_at": datetime.now().isoformat(),
    }


@app.get("/api/bills")
async def get_bills(
    status: str | None = Query(None, description="Filter by status"),
    sector: str | None = Query(None, description="Filter by sector"),
    q: str | None = Query(None, description="Search bills by keyword"),
    limit: int = Query(50, le=200),
):
    bills = db.get_bills(status_filter=status, limit=limit)

    # Sector filter
    if sector:
        bills = [b for b in bills if b.get("sector") == sector]

    # Keyword search
    if q:
        ql = q.lower()
        bills = [
            b for b in bills
            if ql in (b.get("title") or "").lower()
            or ql in (b.get("summary_en") or "").lower()
            or ql in (b.get("raw_text") or "").lower()
        ]

    # Enrich with parsed key facts
    for b in bills:
        b["key_facts_list"] = parse_key_facts(b.get("key_facts"))

    return {"bills": bills, "count": len(bills)}


@app.get("/api/bills/{bill_id}")
async def get_bill(bill_id: str):
    bill = db.get_bill(bill_id)
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    bill["key_facts_list"] = parse_key_facts(bill.get("key_facts"))
    return bill


@app.get("/api/gazette")
async def get_gazette(limit: int = Query(30, le=100)):
    notices = db.get_gazette_notices(limit=limit)
    return {"notices": notices, "count": len(notices)}


@app.get("/api/executive")
async def get_executive_actions(limit: int = Query(30, le=100)):
    actions = db.get_executive_actions(limit=limit)
    return {"actions": actions, "count": len(actions)}


@app.get("/api/parliament/mps")
async def get_mps(limit: int = Query(100, le=350)):
    mps = db.get_mps(limit=limit)
    return {"mps": mps, "count": len(mps)}


@app.get("/api/projections/{horizon}")
async def get_projections(horizon: str):
    """Static projection data by horizon year."""
    valid = {"2027", "2030", "2035", "2045"}
    if horizon not in valid:
        raise HTTPException(400, f"Horizon must be one of {valid}")

    projections_path = Path("jicho/data/projections.json")
    if projections_path.exists():
        data = json.loads(projections_path.read_text())
        return data.get(horizon, {})
    return {"horizon": horizon, "rows": []}


@app.get("/api/scorecard")
async def get_scorecard():
    """2027 election scorecard data."""
    scorecard_path = Path("jicho/data/scorecard.json")
    if scorecard_path.exists():
        return json.loads(scorecard_path.read_text())
    return {
        "days_to_election": days_to_election(),
        "leaders": [],
        "methodology": "Pledge tracking based on Kenya Kwanza 2022 manifesto."
    }


@app.post("/api/admin/run-pipeline")
async def run_pipeline_manual(secret: str = Query(...)):
    """Manually trigger scrape + summarise. Protected by secret key."""
    expected = os.environ.get("ADMIN_SECRET", "")
    if not expected or secret != expected:
        raise HTTPException(403, "Invalid secret")
    import threading
    t = threading.Thread(target=full_pipeline, daemon=True)
    t.start()
    return {"status": "Pipeline started in background"}


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "time": datetime.now().isoformat(),
        "days_to_election": days_to_election(),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
