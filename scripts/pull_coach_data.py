#!/usr/bin/env python3
"""
pull_coach_data.py — Fetch coach hub data for all athletes from intervals.icu.
Writes data/coach.json consumed by coach-hub/index.html.

Usage:
    python scripts/pull_coach_data.py
"""

import json, os, requests
from datetime import date, timedelta, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
OUT_FILE  = REPO_ROOT / "data" / "coach.json"

API_KEY = os.environ.get("INTERVALS_API_KEY", "6123b5w739ctaytjstmw7kmn6").strip()
AUTH    = ("API_KEY", API_KEY)
BASE    = "https://intervals.icu/api/v1/athlete"

# ── Athlete roster ────────────────────────────────────────────────────────────
# Add athletes here as they join intervals.icu
ATHLETES = [
    {
        "id":    "i445042",
        "name":  "Sean Helmot",
        "races": [
            {"name": "Lakeside 10K",      "date": "2026-07-26"},
            {"name": "Melbourne Marathon", "date": "2026-10-11"},
        ],
        "training_philosophy": "HR-primary, pace secondary. Aerobic base first, sharpen closer to race. Easy runs and long runs Z1-Z2 HR. Quality 1-2x per week. Long run progressive HR blocks.",
        "threshold_hr":  165,
        "max_hr":        177,
        "threshold_pace": "4:22",  # derived from Jan-Feb tempo data, mid-block conservative
        "typical_week": {
            "Mon": "Rest",
            "Tue": "Easy run + drills (8-10km Z1-Z2 HR)",
            "Wed": "Quality session (threshold reps or intervals, 10-12km total)",
            "Thu": "Easy run + drills, gym legs PM (8km Z1-Z2 HR)",
            "Fri": "Easy run + flat strides (9-10km Z1-Z2 HR)",
            "Sat": "Easy run — pre-LR activation (6-8km Z1-Z2 HR)",
            "Sun": "Long run (20-32km, progressive HR blocks)",
        },
    },
    {
        "id":    "i620475",
        "name":  "Stacey Harfield",
        "races": [
            {"name": "Gold Coast Marathon", "date": "2026-07-05"},
        ],
        "training_philosophy": "HR-capped easy runs, explicit pace targets for quality. Joe Friel 7-zone system. LTHR 180, MaxHR 197.",
        "threshold_hr":  180,
        "max_hr":        197,
        "threshold_pace": "5:40",
        "typical_week": {},
    },
    {
        "id":    "i620570",
        "name":  "Chess",
        "races": [],
        "training_philosophy": "HR-capped easy runs. Joe Friel 7-zone system. LTHR 170, MaxHR 188. London Marathon 2023: 3:10 (4:27/km avg, 164 avg HR).",
        "threshold_hr":  170,
        "max_hr":        188,
        "threshold_pace": "4:15",
        "typical_week": {},
    },
    {
        "id":    "i619779",
        "name":  "Drakes",
        "races": [],
        "training_philosophy": "",
        "threshold_hr":  163,
        "max_hr":        180,
        "threshold_pace": "4:10",
        "typical_week": {},
    },
    {
        "id":    "i620736",
        "name":  "Rohan Cooper",
        "races": [
            {"name": "Lakeside 10K",       "date": "2026-07-26"},
            {"name": "Melbourne Marathon",  "date": "2026-09-20"},
        ],
        "training_philosophy": "",
        "threshold_hr":  162,
        "max_hr":        170,
        "threshold_pace": "4:05",
        "typical_week": {},
    },
    {
        "id":    "i622562",
        "name":  "Matt W",
        "races": [
            {"name": "Lakeside 10K", "date": "2026-07-26"},
        ],
        "training_philosophy": "",
        "threshold_hr":  165,
        "max_hr":        183,
        "threshold_pace": "4:38",
        "typical_week": {},
    },
    {
        "id":    "i622855",
        "name":  "Tim L",
        "races": [],
        "training_philosophy": "",
        "threshold_hr":  None,
        "max_hr":        None,
        "threshold_pace": None,
        "typical_week": {},
    },
    {
        "id":    "i624875",
        "name":  "Annette",
        "races": [],
        "training_philosophy": "",
        "threshold_hr":  None,
        "max_hr":        None,
        "threshold_pace": None,
        "typical_week": {},
    },
    {
        "id":    "i621769",
        "name":  "Simon Walker",
        "races": [
            {"name": "Lakeside 10K",     "date": "2026-07-26"},
            {"name": "Sydney Marathon",  "date": "2026-08-30"},
        ],
        "training_philosophy": "Triathlon background. Runs 5 days/week. HR-capped easy running, threshold work 1-2x/week. Strong aerobic base from multi-sport history.",
        "threshold_hr":  145,
        "max_hr":        160,
        "threshold_pace": "4:38",
        "typical_week": {
            "Mon": "Rest",
            "Tue": "Easy run (Z1-Z2 HR)",
            "Wed": "Quality session (threshold or CV intervals)",
            "Thu": "Easy run (Z1-Z2 HR)",
            "Fri": "Easy run (Z1-Z2 HR)",
            "Sat": "Easy run or fartlek",
            "Sun": "Long run (easy/mod HR)",
        },
    },
    {
        "id":    "i620541",
        "name":  "Brad P",
        "races": [],
        "training_philosophy": "",
        "threshold_hr":  None,
        "max_hr":        None,
        "threshold_pace": None,
        "typical_week": {},
    },
    {
        "id":    "i624989",
        "name":  "Mark M",
        "races": [],
        "training_philosophy": "",
        "threshold_hr":  None,
        "max_hr":        None,
        "threshold_pace": None,
        "typical_week": {},
    },
    {
        "id":    "i621545",
        "name":  "Sam",
        "races": [],
        "training_philosophy": "Pace-primary quality. LTHR 177, MaxHR 196. HM debut 1:27:25 (4:08/km, 174 avg HR). Strong threshold base — 6x mile @ ~3:58/km. CV capacity 3:45-3:52/km.",
        "threshold_hr":  177,
        "max_hr":        196,
        "threshold_pace": "3:58",
        "typical_week": {},
    },
    {
        "id":    "i625671",
        "name":  "Aidan Burrell",
        "races": [],
        "training_philosophy": "Inexperienced runner building base fitness. Conservative pacing, HR-capped easy runs. Focus on consistency and injury prevention.",
        "threshold_hr":  None,
        "max_hr":        None,
        "threshold_pace": "4:50",
        "typical_week": {},
    },
]

TODAY       = date.today()
WEEK_AGO    = TODAY - timedelta(7)
TWO_WEEKS   = TODAY - timedelta(14)
SIXTY_DAYS  = TODAY - timedelta(60)

def get(path, params=None):
    r = requests.get(f"{BASE}/{path}", auth=AUTH, params=params, timeout=20)
    return r.json() if r.ok else None

def pace_from_speed(mps):
    if not mps or mps < 0.5:
        return None
    spk = 1000 / mps
    mins = int(spk // 60)
    secs = int(spk % 60)
    return mins + secs / 100

def fmt_pace(dec):
    if dec is None:
        return None
    mins = int(dec)
    secs = round((dec % 1) * 100)
    return f"{mins}:{secs:02d}"

def pull_athlete(a):
    aid = a["id"]
    print(f"  Pulling {a['name']} ({aid})…")

    # Profile
    profile = get(aid) or {}

    # Wellness — last 60 days (for HRV4Training-style baseline)
    wellness = get(f"{aid}/wellness", {
        "oldest": str(SIXTY_DAYS), "newest": str(TODAY)
    }) or []

    # Sort wellness by date
    wellness = sorted(wellness, key=lambda w: w["id"])

    # Compute 7-day HRV avg
    hrv_vals = [w["hrv"] for w in wellness[-7:] if w.get("hrv")]
    hrv_7d   = round(sum(hrv_vals) / len(hrv_vals)) if hrv_vals else None

    # HRV4Training 60-day baseline: mean + SD for gauge bar normalisation
    hrv_60d_vals = [w["hrv"] for w in wellness if w.get("hrv")]
    hrv_60d_baseline = None
    hrv_60d_sd       = None
    if len(hrv_60d_vals) >= 7:
        _mu = sum(hrv_60d_vals) / len(hrv_60d_vals)
        _sd = (sum((v - _mu) ** 2 for v in hrv_60d_vals) / len(hrv_60d_vals)) ** 0.5
        hrv_60d_baseline = round(_mu, 1)
        hrv_60d_sd       = round(_sd, 1)

    # Today's wellness
    today_w  = next((w for w in reversed(wellness) if w["id"] == str(TODAY)), None) or \
               (wellness[-1] if wellness else {})

    rhr         = today_w.get("restingHR")
    hrv_today   = today_w.get("hrv")
    sleep_score = today_w.get("sleepScore")
    sleep_secs  = today_w.get("sleepSecs")
    sleep_hrs   = round(sleep_secs / 3600, 1) if sleep_secs else None
    vo2max      = today_w.get("vo2max")
    weight      = today_w.get("weight")
    ctl         = today_w.get("ctl")
    atl         = today_w.get("atl")
    tsb         = round(ctl - atl, 1) if ctl and atl else None

    # CTL/ATL/TSB 7-day trends
    w7ago = next((w for w in reversed(wellness) if w["id"] <= str(WEEK_AGO)), None) or {}
    ctl_7d_ago = w7ago.get("ctl")
    atl_7d_ago = w7ago.get("atl")
    tsb_7d_ago = round(ctl_7d_ago - atl_7d_ago, 1) if ctl_7d_ago and atl_7d_ago else None
    ctl_trend  = round(ctl - ctl_7d_ago, 1) if ctl and ctl_7d_ago else None
    atl_trend  = round(atl - atl_7d_ago, 1) if atl and atl_7d_ago else None
    tsb_trend  = round(tsb - tsb_7d_ago, 1) if tsb is not None and tsb_7d_ago is not None else None

    # RHR trend — flag if elevated vs 7d avg
    rhr_vals  = [w["restingHR"] for w in wellness[-7:] if w.get("restingHR")]
    rhr_7d    = round(sum(rhr_vals) / len(rhr_vals), 1) if rhr_vals else None
    rhr_delta = round(rhr - rhr_7d, 1) if rhr and rhr_7d else None

    # HRV trend — last 3 vs prior 3
    hrv_all = [w["hrv"] for w in wellness if w.get("hrv")]
    hrv_trend = None
    if len(hrv_all) >= 6:
        avg = lambda arr: sum(arr) / len(arr)
        hrv_trend = round(avg(hrv_all[-3:]) - avg(hrv_all[-6:-3]), 1)

    # Recent activities — last 14 days
    acts_raw = get(f"{aid}/activities", {
        "oldest": str(TWO_WEEKS), "newest": str(TODAY)
    }) or []

    activities = []
    for act in acts_raw[:10]:
        if act.get("type") not in ("Run", "TrailRun", "Treadmill"):
            continue
        dist = (act.get("icu_distance") or act.get("distance") or 0) / 1000
        pace = pace_from_speed(act.get("average_speed"))
        activities.append({
            "date":       act["start_date_local"][:10],
            "name":       act.get("name", "Run"),
            "type":       act.get("type"),
            "dist_km":    round(dist, 1) if dist else None,
            "duration_s": act.get("moving_time") or act.get("elapsed_time"),
            "pace":       pace,
            "avg_hr":     act.get("average_heartrate"),
            "max_hr":     act.get("max_heartrate"),
            "feel":       act.get("feel"),
            "effort":     act.get("perceived_exertion"),
            "ctl":        act.get("icu_ctl"),
            "atl":        act.get("icu_atl"),
        })

    # Upcoming planned workouts — next 7 days
    events_raw = get(f"{aid}/events", {
        "oldest": str(TODAY), "newest": str(TODAY + timedelta(7))
    }) or []

    upcoming = []
    for ev in events_raw:
        if ev.get("category") != "WORKOUT":
            continue
        upcoming.append({
            "id":          ev.get("id"),
            "date":        ev["start_date_local"][:10],
            "name":        ev.get("name", ""),
            "description": ev.get("description", ""),
            "type":        ev.get("type"),
            "distance_m":  ev.get("distance"),
        })

    # Flags
    flags = []

    if rhr_delta and rhr_delta > 5:
        flags.append({"level": "red",   "text": f"RHR +{rhr_delta}bpm above 7d avg"})
    elif rhr_delta and rhr_delta > 3:
        flags.append({"level": "amber", "text": f"RHR +{rhr_delta}bpm above 7d avg"})

    if hrv_trend is not None and hrv_trend < -5:
        flags.append({"level": "red",   "text": f"HRV dropping {hrv_trend}ms (3d trend)"})
    elif hrv_trend is not None and hrv_trend < -2:
        flags.append({"level": "amber", "text": f"HRV dropping {hrv_trend}ms (3d trend)"})

    recent_sleep = [w["sleepScore"] for w in wellness[-2:] if w.get("sleepScore")]
    if len(recent_sleep) == 2 and all(s < 65 for s in recent_sleep):
        flags.append({"level": "amber", "text": "Poor sleep ×2 nights"})

    if tsb is not None and tsb < -20:
        flags.append({"level": "amber", "text": f"High fatigue (TSB {tsb})"})

    if activities:
        last_run = date.fromisoformat(activities[0]["date"])
        gap = (TODAY - last_run).days
        if gap >= 3:
            flags.append({"level": "amber", "text": f"No run in {gap} days"})

    # Pull live threshold pace from intervals.icu (m/s → sec/km)
    # Uses /api/v1/activity/{id} — note: not under /athlete/ path
    live_threshold_mps = None
    for act in acts_raw[:5]:
        if act.get("type") in ("Run", "TrailRun"):
            r = requests.get(
                f"https://intervals.icu/api/v1/activity/{act['id']}",
                auth=AUTH, timeout=15
            )
            if r.ok:
                tp_mps = r.json().get("threshold_pace")
                if tp_mps and tp_mps > 0.5:
                    live_threshold_mps = tp_mps
                    break

    def predict_races(config_pace_str, live_mps=None, vo2max_val=None, tsb_val=None):
        """
        Race predictions using three signals, blended:
        1. Threshold pace (Riegel formula extrapolation — T-pace ≈ 60-min race effort)
        2. VO2max (Jack Daniels VDOT tables, simplified polynomial fit)
        3. TSB adjustment — fatigue shifts predictions conservatively

        Riegel: T2 = T1 × (D2/D1)^1.06  (endurance exponent)
        Anchor: threshold pace ≈ half-marathon race pace for well-trained runners
        """
        estimates = []

        def fmt_time(total_secs):
            total_secs = int(total_secs)
            h, m, s = total_secs // 3600, (total_secs % 3600) // 60, total_secs % 60
            return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

        def riegel(anchor_dist_km, anchor_time_s, target_dist_km):
            return anchor_time_s * (target_dist_km / anchor_dist_km) ** 1.06

        # Signal 1: config threshold pace (coach-verified baseline)
        tp_sec_per_km = None
        if config_pace_str:
            try:
                mins, secs = map(int, config_pace_str.split(":"))
                tp_sec_per_km = mins * 60 + secs
            except Exception:
                pass

        # Blend in live threshold from intervals.icu if within 25 sec/km of config
        # (per-activity threshold is noisy; cap its influence to avoid outliers)
        if live_mps and live_mps > 0.5:
            live_sec_per_km = 1000 / live_mps
            if tp_sec_per_km is None:
                tp_sec_per_km = live_sec_per_km
            elif abs(live_sec_per_km - tp_sec_per_km) <= 25:
                tp_sec_per_km = 0.7 * tp_sec_per_km + 0.3 * live_sec_per_km

        if tp_sec_per_km:
            # T-pace ≈ 10K race pace for most recreational runners.
            # Anchor on 10K, then Riegel to other distances.
            # This is more conservative than anchoring on HM and avoids
            # the compounding optimism of Riegel over very long distances.
            ten_k_time_s = tp_sec_per_km * 10
            estimates.append({
                "5k":       riegel(10, ten_k_time_s, 5),
                "10k":      ten_k_time_s,
                "half":     riegel(10, ten_k_time_s, 21.1),
                "marathon": riegel(10, ten_k_time_s, 42.2),
            })

        # Signal 2: VO2max → VDOT (Daniels polynomial, sec for each distance)
        # Fit: VDOT 40-70 range, calibrated against Daniels tables
        if vo2max_val and 30 < vo2max_val < 85:
            v = vo2max_val
            vdot_5k   = (-4.6e-4 * v**3 + 0.0748 * v**2 - 5.07 * v + 1437)   # sec
            vdot_10k  = riegel(5, vdot_5k, 10)
            vdot_half = riegel(5, vdot_5k, 21.1)
            vdot_mar  = riegel(5, vdot_5k, 42.2)
            estimates.append({
                "5k":       vdot_5k,
                "10k":      vdot_10k,
                "half":     vdot_half,
                "marathon": vdot_mar,
            })

        if not estimates:
            return {}, None

        # Blend signals (simple average if both available)
        keys = ["5k", "10k", "half", "marathon"]
        blended = {}
        for k in keys:
            vals = [e[k] for e in estimates if k in e]
            blended[k] = sum(vals) / len(vals)

        # Signal 3: TSB adjustment — if fatigued, add conservative buffer
        tsb_note = ""
        if tsb_val is not None:
            if tsb_val < -20:
                factor = 1.015   # ~1.5% slower when heavily fatigued
                blended = {k: v * factor for k, v in blended.items()}
                tsb_note = "adjusted for fatigue"
            elif tsb_val > 10:
                factor = 0.995   # ~0.5% faster when fresh/peaked
                blended = {k: v * factor for k, v in blended.items()}
                tsb_note = "adjusted for freshness"

        method = "threshold pace" if tp_sec_per_km else ""
        if vo2max_val:
            method = (method + " + VO2max").lstrip(" + ")
        if tsb_note:
            method += f", {tsb_note}"

        return {k: fmt_time(v) for k, v in blended.items()}, method

    predictions, pred_method = predict_races(
        a.get("threshold_pace"),
        live_mps=live_threshold_mps,
        vo2max_val=vo2max,
        tsb_val=tsb,
    )

    # Races — compute days to each, attach relevant prediction
    races = []
    for r in (a.get("races") or []):
        rd = date.fromisoformat(r["date"])
        name_lower = r["name"].lower()
        pred_key = "10k" if "10k" in name_lower else "half" if "half" in name_lower else "marathon" if "marathon" in name_lower else None
        predicted = predictions.get(pred_key)
        races.append({
            **r,
            "days_away":       (rd - TODAY).days,
            "predicted_time":  predicted,
        })

    # Primary race (soonest future race)
    future_races = [r for r in races if r["days_away"] >= 0]
    next_race     = future_races[0] if future_races else None

    return {
        "id":                   aid,
        "name":                 a["name"],
        "race":                 next_race["name"] if next_race else None,
        "race_date":            next_race["date"] if next_race else None,
        "days_to_race":         next_race["days_away"] if next_race else None,
        "races":                races,
        "race_predictions":     predictions,
        "race_predictions_method": pred_method,
        "training_philosophy":  a.get("training_philosophy"),
        "typical_week":         a.get("typical_week"),
        "health": {
            "wellness_date":    today_w.get("id"),
            "rhr":              rhr,
            "rhr_7d_avg":       rhr_7d,
            "rhr_delta":        rhr_delta,
            "hrv_today":        hrv_today,
            "hrv_7d_avg":       hrv_7d,
            "hrv_60d_baseline": hrv_60d_baseline,
            "hrv_60d_sd":       hrv_60d_sd,
            "hrv_60d_n":        len(hrv_60d_vals),
            "hrv_trend":        hrv_trend,
            "sleep_score":      sleep_score,
            "sleep_hrs":        sleep_hrs,
            "vo2max":           vo2max,
            "weight":           weight,
        },
        "fitness": {
            "ctl":       round(ctl, 1) if ctl else None,
            "atl":       round(atl, 1) if atl else None,
            "tsb":       tsb,
            "ctl_trend": ctl_trend,
            "atl_trend": atl_trend,
            "tsb_trend": tsb_trend,
        },
        "wellness_60d": [
            {
                "date":        w["id"],
                "rhr":         w.get("restingHR"),
                "hrv":         w.get("hrv"),
                "sleep_score": w.get("sleepScore"),
                "sleep_hrs":   round(w["sleepSecs"] / 3600, 1) if w.get("sleepSecs") else None,
                "ctl":         round(w["ctl"], 1) if w.get("ctl") else None,
                "atl":         round(w["atl"], 1) if w.get("atl") else None,
            }
            for w in wellness
        ],
        "recent_activities": activities,
        "upcoming":          upcoming,
        "flags":             flags,
    }


def main():
    print(f"Pulling coach data for {len(ATHLETES)} athlete(s)…")
    athletes_data = []
    for a in ATHLETES:
        try:
            athletes_data.append(pull_athlete(a))
        except Exception as e:
            print(f"  ERROR {a['name']}: {e}")
            athletes_data.append({
                "id": a["id"], "name": a["name"],
                "error": str(e), "flags": []
            })

    out = {
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "athletes":     athletes_data,
    }
    OUT_FILE.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_FILE}")


if __name__ == "__main__":
    main()
