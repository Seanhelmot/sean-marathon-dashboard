#!/usr/bin/env python3
"""
pull_garmin.py — Pulls training data from Garmin Connect and writes data/live.json.

On success: overwrites data/live.json with fresh data and exits 0.
On failure: logs the error, leaves data/live.json untouched, exits 1.

Required env vars:
  GARMIN_EMAIL
  GARMIN_PASSWORD
  GARMIN_SESSION_TOKEN  (optional but preferred — avoids full login round-trip)

Run locally first to generate GARMIN_SESSION_TOKEN, then save it as a GitHub secret.
"""

import json
import os
import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
LIVE_JSON  = REPO_ROOT / "data" / "live.json"
PLAN_JSON  = REPO_ROOT / "data" / "plan.json"

WEEKS_BACK = 8   # how far back to look for weekly aggregates
SLEEP_DAYS = 14  # how many nights of sleep/HRV to include


def login_garth():
    """Authenticate via garth; prefer session token, fall back to email/password."""
    import garth

    token = os.environ.get("GARMIN_SESSION_TOKEN", "").strip()
    email = os.environ.get("GARMIN_EMAIL", "").strip()
    password = os.environ.get("GARMIN_PASSWORD", "").strip()

    if token:
        try:
            garth.resume(token)
            garth.client.username  # raises if session dead
            print("Logged in via session token.")
            return garth
        except Exception as e:
            print(f"Session token invalid ({e}), falling back to email/password.")

    if not email or not password:
        raise RuntimeError(
            "No valid session token and GARMIN_EMAIL/GARMIN_PASSWORD not set."
        )

    garth.login(email, password)
    print("Logged in via email/password.")

    # Print the new token so you can update the GitHub secret.
    print("New session token (update GARMIN_SESSION_TOKEN secret):")
    print(garth.client.dumps())

    return garth


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def monday_of(dt: datetime) -> datetime:
    return dt - timedelta(days=dt.weekday())


def pace_from_speed(speed_m_s: float) -> float | None:
    """Convert m/s to min/km (decimal, e.g. 4.58 = 4:35/km)."""
    if not speed_m_s or speed_m_s <= 0:
        return None
    min_per_km = 1000 / 60 / speed_m_s
    mins = int(min_per_km)
    secs = round((min_per_km - mins) * 60)
    return round(mins + secs / 100, 2)


def pull_data(garth):
    today = datetime.now(timezone.utc).date()
    plan = json.loads(PLAN_JSON.read_text())

    # Determine current build week from plan start.
    # Plan week 1 starts on the Monday that plan.json week 1 maps to.
    # We infer it by counting back from race_date.
    race_date = datetime.strptime(plan["race_date"], "%Y-%m-%d").date()
    build_start = race_date - timedelta(weeks=plan["build_weeks"])
    build_start_monday = build_start - timedelta(days=build_start.weekday())
    current_week = max(1, (today - build_start_monday).days // 7 + 1)

    # ── Activities (last WEEKS_BACK weeks) ────────────────────────────────────
    lookback_start = iso(today - timedelta(weeks=WEEKS_BACK))
    activities_raw = garth.connectapi(
        "/activitylist-service/activities/search/activities",
        params={
            "startDate": lookback_start,
            "endDate": iso(today),
            "activityType": "running",
            "limit": 200,
        },
    )

    # Aggregate by calendar week number relative to build start
    week_buckets: dict[int, dict] = {}

    for act in activities_raw:
        act_date = datetime.strptime(act["startTimeLocal"][:10], "%Y-%m-%d").date()
        act_monday = monday_of(datetime.combine(act_date, datetime.min.time())).date()
        wk_num = (act_monday - build_start_monday).days // 7 + 1
        if wk_num < 1:
            continue

        dist_km = act.get("distance", 0) / 1000
        bucket = week_buckets.setdefault(wk_num, {"actual_km": 0.0, "quality": None})
        bucket["actual_km"] += dist_km

        # Identify quality session: threshold/interval runs by HR or workout type
        avg_hr = act.get("averageHR", 0)
        workout_name = (act.get("activityName") or "").lower()
        is_quality = avg_hr >= 150 or any(
            kw in workout_name for kw in ("threshold", "interval", "tempo", "track", "repeat")
        )
        if is_quality and bucket["quality"] is None:
            speed = act.get("averageSpeed", 0)
            bucket["quality"] = {
                "pace_min_per_km": pace_from_speed(speed),
                "avg_hr": int(avg_hr),
            }

    # Build weeks list (plan weeks that have completed data)
    plan_weeks_with_actual = []
    for pw in plan["weeks"]:
        wk = pw["wk"]
        bucket = week_buckets.get(wk)
        if bucket is None:
            continue
        wk_monday = build_start_monday + timedelta(weeks=wk - 1)
        wk_sunday = wk_monday + timedelta(days=6)
        partial = wk_sunday > today
        plan_weeks_with_actual.append({
            "wk": wk,
            "actual_km": round(bucket["actual_km"], 1),
            "partial": partial,
            "quality": bucket["quality"],
        })

    # ── Today's stats ──────────────────────────────────────────────────────────
    stats = garth.connectapi(f"/usersummary-service/usersummary/daily/{iso(today)}")

    rhr = stats.get("restingHeartRate")
    body_battery = None
    bb_data = garth.connectapi(
        "/wellness-service/wellness/bodyBattery/reports/daily",
        params={"startDate": iso(today), "endDate": iso(today)},
    )
    if bb_data:
        vals = bb_data[0].get("bodyBatteryValueDescriptorDTOList", [])
        if vals:
            body_battery = vals[-1].get("bodyBatteryValue")

    # HRV
    hrv_data = garth.connectapi(
        "/hrv-service/hrv/weekly",
        params={"startDate": iso(today - timedelta(days=7)), "endDate": iso(today)},
    )
    hrv_7d_avg = None
    hrv_status = None
    if hrv_data:
        readings = hrv_data.get("hrvSummaries", [])
        vals = [r["weeklyAvg"] for r in readings if r.get("weeklyAvg")]
        if vals:
            hrv_7d_avg = round(sum(vals) / len(vals))
        hrv_status = (readings[-1].get("status") or "").upper() if readings else None

    # Sleep
    sleep_resp = garth.connectapi(
        "/wellness-service/wellness/dailySleepData",
        params={"date": iso(today - timedelta(days=1))},
    )
    sleep_score = None
    sleep_hrs = None
    if sleep_resp:
        sd = sleep_resp.get("dailySleepDTO", {})
        sleep_score = sd.get("sleepScores", {}).get("overall", {}).get("value")
        total_seconds = sd.get("sleepTimeSeconds", 0)
        if total_seconds:
            sleep_hrs = round(total_seconds / 3600, 1)

    # VO2max
    vo2_resp = garth.connectapi("/metrics-service/metrics/maxmet/daily", params={"startDate": iso(today), "endDate": iso(today)})
    vo2max = None
    if vo2_resp and isinstance(vo2_resp, list):
        entry = vo2_resp[-1] if vo2_resp else {}
        vo2max = entry.get("generic", {}).get("vo2MaxPreciseValue") or entry.get("running", {}).get("vo2MaxPreciseValue")
        if vo2max:
            vo2max = round(float(vo2max))

    # ── Sleep & HRV last N nights ─────────────────────────────────────────────
    sleep_hrv_14d = []
    for offset in range(SLEEP_DAYS - 1, -1, -1):
        night = today - timedelta(days=offset)
        try:
            sr = garth.connectapi(
                "/wellness-service/wellness/dailySleepData",
                params={"date": iso(night)},
            )
            if not sr:
                continue
            sd = sr.get("dailySleepDTO", {})
            sc = sd.get("sleepScores", {}).get("overall", {}).get("value")

            hrv_r = garth.connectapi(
                "/hrv-service/hrv",
                params={"date": iso(night)},
            )
            overnight_hrv = None
            if hrv_r:
                overnight_hrv = hrv_r.get("hrvSummary", {}).get("overnight")

            if sc is not None or overnight_hrv is not None:
                sleep_hrv_14d.append({
                    "date": iso(night),
                    "score": sc,
                    "hrv": overnight_hrv,
                })
        except Exception:
            pass

    # ── Assemble live.json ────────────────────────────────────────────────────
    live = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "current_week": current_week,
        "today": {
            "rhr": rhr,
            "hrv_7d_avg": hrv_7d_avg,
            "hrv_status": hrv_status,
            "sleep_score": sleep_score,
            "sleep_hrs": sleep_hrs,
            "body_battery": body_battery,
            "vo2max_garmin": vo2max,
            "vo2max_note": "lab-tested 58.4 (2022)",
        },
        "this_week_days": None,  # not auto-generated; update manually or extend script
        "weeks": plan_weeks_with_actual,
        "sleep_hrv_14d": sleep_hrv_14d,
    }

    return live


def main():
    try:
        garth = login_garth()
    except Exception:
        print("ERROR: Garmin login failed.", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)

    try:
        live = pull_data(garth)
    except Exception:
        print("ERROR: Data pull failed. Leaving live.json untouched.", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)

    LIVE_JSON.write_text(json.dumps(live, indent=2))
    print(f"Wrote {LIVE_JSON} — {len(live['weeks'])} weeks, {len(live['sleep_hrv_14d'])} sleep nights.")


if __name__ == "__main__":
    main()
