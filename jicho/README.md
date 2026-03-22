# Jicho la Wananchi — Kenya Civic Tracker

> *"The People's Eye"* — Tracking what Kenya's government does, in plain language.

A live civic education platform that scrapes bills, gazette notices, and executive actions from Kenyan government sources, summarises them using Claude AI into plain English and Kiswahili, and serves them through a public dashboard.

---

## Deploy in 5 steps (no coding required)

### Step 1 — Get a free GitHub account
If you don't have one: https://github.com/signup

### Step 2 — Create a new GitHub repository
1. Go to https://github.com/new
2. Name it `jicho-wananchi`
3. Set it to **Public**
4. Click **Create repository**

### Step 3 — Upload the project files
Upload all files from this folder maintaining the structure:
```
jicho-wananchi/
├── main.py
├── database.py
├── scraper.py
├── summariser.py
├── requirements.txt
├── render.yaml
├── templates/
│   └── dashboard.html
└── data/
    ├── projections.json
    └── scorecard.json
```

### Step 4 — Deploy on Render (free)
1. Go to https://render.com and sign up (free, no credit card)
2. Click **New → Web Service**
3. Connect your GitHub account and select `jicho-wananchi`
4. Render will auto-detect the `render.yaml` config
5. You'll see one required environment variable: `ANTHROPIC_API_KEY`
6. Get your key from: https://console.anthropic.com/keys
7. Paste it in and click **Deploy**

Your app will be live at: `https://jicho-wananchi.onrender.com`

### Step 5 — First run
On first deploy, the app automatically:
1. Creates the database
2. Seeds it with current Kenyan bills and gazette notices
3. Runs the AI summarisation engine to generate English + Kiswahili summaries
4. Schedules nightly scrapes at 02:00 EAT

---

## Architecture

```
Data sources (parliament.go.ke, kenyalaw.org, president.go.ke)
    ↓
scraper.py  — fetches bills, gazette notices, executive actions
    ↓
summariser.py — Claude API generates plain-language summaries (EN + SW)
    ↓
database.py — SQLite storage (jicho.db)
    ↓
main.py (FastAPI) — serves dashboard + JSON API
    ↓
templates/dashboard.html — public civic dashboard
```

## API endpoints

| Endpoint | Description |
|---|---|
| `GET /` | Public dashboard |
| `GET /api/stats` | Summary stats (bills count, days to election) |
| `GET /api/bills` | All bills (filter: `?status=passed`, `?q=housing`) |
| `GET /api/bills/{id}` | Single bill detail |
| `GET /api/gazette` | Gazette notices |
| `GET /api/executive` | Executive actions |
| `GET /api/projections/{year}` | Impact projections (2027/2030/2035/2045) |
| `GET /api/scorecard` | 2027 election scorecard |
| `GET /api/health` | Health check |
| `POST /api/admin/run-pipeline?secret=X` | Manually trigger scrape + summarise |

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | ✅ Yes | From console.anthropic.com |
| `ADMIN_SECRET` | Auto-generated | For manual pipeline trigger |
| `PORT` | Auto-set by Render | Web server port |

## Updating content

### Adding a new bill manually
Edit `data/scorecard.json` or trigger the pipeline via:
```
POST /api/admin/run-pipeline?secret=YOUR_ADMIN_SECRET
```

### Updating scorecard data
Edit `data/scorecard.json` — push to GitHub — Render auto-deploys.

### Updating projections
Edit `data/projections.json` — push to GitHub.

## Data sources

- **National Assembly bills**: http://www.parliament.go.ke + https://www.kenyalaw.org
- **Kenya Gazette**: https://www.kenyalaw.org/kl/
- **State House press releases**: https://www.president.go.ke
- **National Treasury**: https://www.treasury.go.ke

## Non-partisan commitment

This platform:
- Shows **raw facts only** — no scores, no ratings, no editorial positions
- Cites sources for every claim
- Provides both English and Kiswahili summaries
- Is open source and open data
- Carries no advertising

---

*Built for every Kenyan citizen. Jicho la Wananchi — The People's Eye.*
