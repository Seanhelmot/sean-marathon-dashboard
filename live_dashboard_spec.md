# Live Marathon Dashboard — Build Spec

**Goal:** a dashboard that looks like the one already built, but refreshes itself on a schedule instead of being a frozen snapshot. No server to run or pay for.

**Approach (Tier 2):** a scheduled job pulls Garmin data → writes JSON into the repo → a static site reads the JSON → hosted free on GitHub Pages.

---

## 1. Repo structure

```
sean-marathon-dashboard/
├── .github/workflows/
│   └── refresh-data.yml      # the scheduled job
├── scripts/
│   └── pull_garmin.py        # pulls data, writes JSON
├── data/
│   ├── plan.json             # static — the 22-week plan, edit by hand when plan changes
│   └── live.json             # generated — overwritten every run, DO NOT hand-edit
├── index.html                # the dashboard (adapt the one already built)
└── README.md
```

## 2. Credentials — do this first, do it right

Garmin Connect has no public API. The pull script uses an unofficial library (`garminconnect` or `garth` on PyPI) that logs in with your Garmin username/password.

- **Never commit credentials to the repo**, not even in a `.env` file that's gitignored — mistakes happen.
- Store them as **GitHub Actions encrypted secrets**: repo → Settings → Secrets and variables → Actions → New repository secret.
  - `GARMIN_EMAIL`
  - `GARMIN_PASSWORD`
- `garth` (the more modern library) supports saving a session token after first login, so the workflow isn't re-authenticating from scratch every run. Save that token as a third secret (`GARMIN_SESSION_TOKEN`) once you've logged in locally the first time, so the Action reuses it. This also reduces how often Garmin's login flow (which can trigger MFA/captcha) gets hit.

## 3. The pull script (`scripts/pull_garmin.py`)

Responsibilities:
1. Authenticate (session token first, fall back to email/password).
2. Pull, for roughly the last 8 weeks:
   - Running activities (date, distance, duration, avg/max HR) → derive weekly volume and quality-session pace/HR.
   - HRV trend.
   - Sleep summaries (last ~14 nights).
   - Training load / VO2max trend.
   - Today's stats (RHR, body battery, stress).
3. Compute the derived fields the dashboard needs (weekly totals, quality-session pace in min/km, etc.) — do this in Python, not in the browser, so the site stays a dumb renderer.
4. Write the result to `data/live.json`, overwriting the previous version.
5. **On failure** (Garmin API down, login broken, rate-limited): exit non-zero but leave `live.json` untouched, so the site keeps showing the last good pull rather than breaking. Log the error to the Action's output so you notice in GitHub's UI.

Suggested `live.json` shape:

```json
{
  "generated_at": "2026-06-19T08:00:00Z",
  "today": { "rhr": 41, "hrv_7d_avg": 77, "hrv_status": "BALANCED", "sleep_score": 76, "body_battery": 39 },
  "weeks": [
    { "week": 1, "actual_km": 58.6, "long_run_km": 18, "quality": null },
    { "week": 6, "actual_km": 49.2, "partial": true, "quality": { "pace_min_per_km": 4.58, "avg_hr": 156 } }
  ],
  "sleep_hrv_14d": [ { "date": "2026-06-13", "score": 62, "hrv": 80 } ]
}
```

`data/plan.json` stays static — it's the 22-week structure (phases, planned volume, long runs, quality sessions) from the plan doc. Re-export it by hand if the plan changes; no reason to regenerate it every run.

## 4. The scheduled job (`.github/workflows/refresh-data.yml`)

- Trigger: `schedule` (cron) — every 6 hours is plenty for a training dashboard; running data doesn't change faster than that. Add `workflow_dispatch` too, so you can manually trigger a refresh from GitHub's UI after a run instead of waiting.
- Steps: checkout → set up Python → install deps → run `pull_garmin.py` with the secrets as env vars → commit `data/live.json` back to the repo if it changed → push.
- GitHub Pages auto-redeploys on push, so a successful run = updated site within a minute or two.

## 5. The site (`index.html`)

Reuse the dashboard already built — same structure, same charts — but instead of data baked into the JS, `fetch('./data/plan.json')` and `fetch('./data/live.json')` on page load and render from that. Everything else (the SVG chart functions, the layout, the styling) carries over directly.

## 6. Hosting

- GitHub Pages, repo → Settings → Pages → deploy from the `main` branch root (or a `/docs` folder if you prefer). Free, no separate hosting account needed.
- You get a real URL: `https://<username>.github.io/sean-marathon-dashboard/` — bookmark-able on your phone, shareable with Mohsin if useful.

## 7. What "live" actually means here

Refreshes every 6 hours (or whenever you manually trigger it), not instantaneous. For a training dashboard that's checked once or twice a day, that's indistinguishable from real-time in practice — there's no reason to poll more aggressively, and doing so increases the chance of Garmin's login flow flagging the automated traffic.

## 8. Known maintenance burden — be honest with yourself about this

Garmin's API is unofficial and reverse-engineered. It breaks occasionally when Garmin changes something on their end, which means the Action will start failing silently until you notice the site's gone stale. Worth checking the Actions tab every couple of weeks during the build, more often close to race day when you'll actually be relying on it.

---

**Handoff note for Claude Code:** give it this file plus the existing `sean_marathon_dashboard.html` as the starting point for the front end, and ask it to scaffold the repo structure above.
