#!/usr/bin/env python3
"""
pull_garmin.py — Pulls training data from Garmin Connect and writes data/live.json.

On success: overwrites data/live.json with fresh data and exits 0.
On failure: logs the error, leaves data/live.json untouched, exits 1.

Required env vars:
  GARMIN_EMAIL
  GARMIN_PASSWORD

Install deps:
  pip install garminconnect
"""

import json
import os
import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT  = Path(__file__).parent.parent
LIVE_JSON  = REPO_ROOT / "data" / "live.json"
PLAN_JSON  = REPO_ROOT / "data" / "plan.json"

WEEKS_BACK = 8
SLEEP_DAYS = 14


def login():
    from garminconnect import Garmin

    email    = os.environ.get("GARMIN_EMAIL", "").strip()
    password = os.environ.get("GARMIN_PASSWORD", "").strip()

    if not email or not password:
        raise RuntimeError("GARMIN_EMAIL and GARMIN_PASSWORD env vars must be set.")

    client = Garmin(email, password)
    client.login()
    print(f"Logged in as {email}")
    return client


def iso(d) -> str:
    return d.strftime("%Y-%m-%d")


def pace_from_speed(speed_m_s: float):
    if not speed_m_s or speed_m_s <= 0:
        return None
    min_per_km = 1000 / 60 / speed_m_s
    mins = int(min_per_km)
    secs = round((min_per_km - mins) * 60)
    return round(mins + secs / 100, 2)


def _work_interval_stats(client, activity_id):
    """
    Fetch lap splits for a quality session and return (pace_min_per_km, avg_hr)
    computed from work laps only (HR >= 150bpm), weighted by distance.
    Returns (None, None) if splits unavailable or no work laps found.
    """
    WORK_HR_FLOOR = 158  # Z4 threshold floor per plan.json hr_zones
    try:
        splits = client.get_activity_splits(activity_id)
        laps = splits.get("lapDTOs") or splits.get("activityLapDTOs") or []
        if not laps:
            return None, None

        work_laps = [
            lap for lap in laps
            if (lap.get("averageHR") or 0) >= WORK_HR_FLOOR
            and (lap.get("distance") or 0) > 200  # ignore sub-200m laps (standing rest)
        ]
        if not work_laps:
            return None, None

        total_dist  = sum(lap["distance"] for lap in work_laps)
        weighted_hr = sum(lap["averageHR"] * lap["distance"] for lap in work_laps) / total_dist
        avg_speed   = total_dist / sum(lap.get("duration", lap.get("elapsedDuration", 0)) for lap in work_laps)

        return pace_from_speed(avg_speed), round(weighted_hr)
    except Exception:
        return None, None


def _decoupling(client, activity_id):
    """
    HR:pace decoupling for a long run.
    Splits laps into first and second half by distance, compares HR/speed ratio.
    Returns % decoupling (positive = HR drifted up relative to pace).
    """
    try:
        splits = client.get_activity_splits(activity_id)
        laps = splits.get("lapDTOs") or splits.get("activityLapDTOs") or []
        laps = [l for l in laps if (l.get("distance") or 0) > 200
                and (l.get("averageHR") or 0) > 100
                and (l.get("averageSpeed") or 0) > 0]
        if len(laps) < 4:
            return None
        total = sum(l["distance"] for l in laps)
        half, cum, first, second = total / 2, 0, [], []
        for l in laps:
            (first if cum < half else second).append(l)
            cum += l["distance"]
        if not first or not second:
            return None
        def ratio(ls):
            d = sum(l["distance"] for l in ls)
            hr = sum(l["averageHR"] * l["distance"] for l in ls) / d
            spd = d / sum(l.get("duration", l.get("elapsedDuration", 1)) for l in ls)
            return hr / spd   # beats per m/s — higher means HR high for speed
        r1, r2 = ratio(first), ratio(second)
        return round((r2 - r1) / r1 * 100, 1)
    except Exception:
        return None


def pull_data(client):
    from zoneinfo import ZoneInfo
    today = datetime.now(ZoneInfo("Australia/Melbourne")).date()
    plan  = json.loads(PLAN_JSON.read_text())

    build_start_mon  = datetime.strptime(plan["build_start_date"], "%Y-%m-%d").date()
    current_week     = max(1, (today - build_start_mon).days // 7 + 1)

    # ── Activities ──────────────────────────────────────────────────────────
    start_date = today - timedelta(weeks=WEEKS_BACK)
    activities = client.get_activities_by_date(iso(start_date), iso(today), "running")

    week_buckets: dict[int, dict] = {}
    recent_activities = []

    for act in activities:
        act_date   = datetime.strptime(act["startTimeLocal"][:10], "%Y-%m-%d").date()
        act_monday = act_date - timedelta(days=act_date.weekday())
        wk_num     = (act_monday - build_start_mon).days // 7 + 1
        if wk_num < 1:
            continue

        dist_km  = (act.get("distance") or 0) / 1000
        avg_hr   = act.get("averageHR") or 0
        max_hr   = act.get("maxHR") or 0
        duration_s = act.get("duration") or 0
        speed    = act.get("averageSpeed") or 0
        # feel/effort live in summaryDTO.directWorkoutFeel/Rpe (0–100 scale)
        feel, effort = None, None
        try:
            detail  = client.get_activity(act["activityId"])
            summary = detail.get("summaryDTO") or {}
            feel_raw   = summary.get("directWorkoutFeel")
            effort_raw = summary.get("directWorkoutRpe")
            if feel_raw is not None:
                feel = max(1, min(5, int((feel_raw - 1) // 20 + 1)))
            if effort_raw is not None:
                effort = round(effort_raw / 10, 1)
        except Exception:
            pass

        bucket = week_buckets.setdefault(wk_num, {"actual_km": 0.0, "quality": None, "days": {}})
        bucket["actual_km"] += dist_km
        # Accumulate per day (multiple Garmin entries on same day e.g. warm-up + main run)
        day_key = iso(act_date)
        existing_day = bucket["days"].get(day_key)
        if existing_day:
            existing_day["dist_km"] = round(existing_day["dist_km"] + dist_km, 1)
            if avg_hr and (existing_day["avg_hr"] is None or dist_km > existing_day.get("_main_dist", 0)):
                existing_day["avg_hr"]  = int(avg_hr)
                existing_day["pace"]    = pace_from_speed(speed)
                existing_day["_main_dist"] = dist_km
                # feel/effort follow the dominant (longest) activity
                if feel   is not None: existing_day["feel"]   = int(feel)
                if effort is not None: existing_day["effort"] = round(float(effort), 1)
        else:
            is_long = dist_km >= 18
            decouple = _decoupling(client, act["activityId"]) if is_long else None
            bucket["days"][day_key] = {
                "dist_km":        round(dist_km, 1),
                "avg_hr":         int(avg_hr) if avg_hr else None,
                "pace":           pace_from_speed(speed),
                "feel":           int(feel) if feel is not None else None,
                "effort":         round(float(effort), 1) if effort is not None else None,
                "decoupling_pct": decouple,
                "_main_dist":     dist_km,
            }

        workout_name = (act.get("activityName") or "").lower()
        is_quality   = avg_hr >= 150 or any(
            kw in workout_name for kw in ("threshold", "interval", "tempo", "track", "repeat")
        )
        if is_quality and bucket["quality"] is None:
            # Try to get work-interval-only pace/HR from lap splits
            work_pace, work_hr = _work_interval_stats(client, act["activityId"])
            bucket["quality"] = {
                "pace_min_per_km": work_pace if work_pace else pace_from_speed(speed),
                "avg_hr":          work_hr   if work_hr   else int(avg_hr),
                "work_intervals_only": work_pace is not None,
            }

        # Build recent activities list (last 14 days)
        if act_date >= today - timedelta(days=14):
            recent_activities.append({
                "date":       iso(act_date),
                "name":       act.get("activityName") or "Run",
                "dist_km":    round(dist_km, 2),
                "duration_s": int(duration_s),
                "avg_hr":     int(avg_hr) if avg_hr else None,
                "max_hr":     int(max_hr) if max_hr else None,
                "pace":       pace_from_speed(speed),
                "feel":       int(feel) if feel is not None else None,
                "effort":     round(float(effort), 1) if effort is not None else None,
                "elevation_gain": act.get("elevationGain"),
                "avg_cadence":    act.get("averageRunningCadenceInStepsPerMinute"),
            })

    recent_activities.sort(key=lambda x: x["date"], reverse=True)

    weeks_out = []
    for pw in plan["weeks"]:
        wk     = pw["wk"]
        bucket = week_buckets.get(wk)
        if bucket is None:
            continue
        wk_monday = build_start_mon + timedelta(weeks=wk - 1)
        partial   = (wk_monday + timedelta(days=6)) > today
        weeks_out.append({
            "wk":        wk,
            "actual_km": round(bucket["actual_km"], 1),
            "partial":   partial,
            "quality":   bucket["quality"],
            "days":      bucket.get("days", {}),
        })

    # ── Today stats ─────────────────────────────────────────────────────────
    stats = client.get_user_summary(iso(today))
    rhr   = stats.get("restingHeartRate")

    # Body battery — use the day's peak (first reading after waking) not current value
    body_battery = None
    try:
        bb = client.get_body_battery(iso(today), iso(today))
        if bb and isinstance(bb, list):
            entries = bb[0].get("bodyBatteryValuesArray") or []
            if entries:
                body_battery = max(v[1] for v in entries if v[1] is not None)
    except Exception:
        pass

    # HRV
    hrv_7d_avg = None
    hrv_status = None
    try:
        hrv = client.get_hrv_data(iso(today))
        summary = hrv.get("hrvSummary") or {}
        hrv_7d_avg = summary.get("weeklyAvg") or summary.get("lastNight")
        if hrv_7d_avg:
            hrv_7d_avg = round(hrv_7d_avg)
        hrv_status = (summary.get("status") or "").upper() or None
    except Exception:
        pass

    # Sleep (last night)
    sleep_score = None
    sleep_hrs   = None
    try:
        yesterday = today - timedelta(days=1)
        sleep = client.get_sleep_data(iso(yesterday))
        sd    = sleep.get("dailySleepDTO") or {}
        sleep_score = (sd.get("sleepScores") or {}).get("overall", {}).get("value")
        secs        = sd.get("sleepTimeSeconds") or 0
        if secs:
            sleep_hrs = round(secs / 3600, 1)
    except Exception:
        pass

    # VO2max
    vo2max = None
    try:
        v = client.get_max_metrics(iso(today))
        if v and isinstance(v, list):
            entry  = v[-1]
            vo2max = (entry.get("generic") or entry.get("running") or {}).get("vo2MaxPreciseValue")
            if vo2max:
                vo2max = round(float(vo2max))
    except Exception:
        pass

    # ── Sleep + HRV last N nights ────────────────────────────────────────────
    sleep_hrv_14d = []
    for offset in range(SLEEP_DAYS - 1, -1, -1):
        night = today - timedelta(days=offset)
        try:
            sr  = client.get_sleep_data(iso(night))
            sd  = (sr.get("dailySleepDTO") or {})
            sc  = (sd.get("sleepScores") or {}).get("overall", {}).get("value")
            hrv_r      = client.get_hrv_data(iso(night))
            hrv_sum    = hrv_r.get("hrvSummary") or {}
            night_hrv  = hrv_sum.get("lastNight") or hrv_sum.get("weeklyAvg")
            if sc is not None or night_hrv is not None:
                sleep_hrv_14d.append({"date": iso(night), "score": sc, "hrv": night_hrv})
        except Exception:
            pass

    # ── This week days — pulled from activities and plan ────────────────────
    # We keep this_week_days as None here; it's hand-authored in live.json
    # and the dashboard falls back to a notice if absent.
    # To auto-populate, extend this section using scheduled workouts API.
    this_week_days = None
    try:
        existing = json.loads(LIVE_JSON.read_text(encoding='utf-8'))
        this_week_days = existing.get("this_week_days")
    except Exception:
        pass

    return {
        "generated_at":    datetime.now(ZoneInfo("Australia/Melbourne")).strftime("%Y-%m-%dT%H:%M:%S+10:00"),
        "current_week":    current_week,
        "today": {
            "rhr":          rhr,
            "hrv_7d_avg":   hrv_7d_avg,
            "hrv_status":   hrv_status,
            "sleep_score":  sleep_score,
            "sleep_hrs":    sleep_hrs,
            "body_battery": body_battery,
            "vo2max_garmin": vo2max,
            "vo2max_note":  "lab-tested 58.4 (2022)",
        },
        "this_week_days":  this_week_days,
        "weeks":              weeks_out,
        "sleep_hrv_14d":      sleep_hrv_14d,
        "recent_activities":  recent_activities,
    }


def main():
    try:
        client = login()
    except Exception:
        print("ERROR: Garmin login failed.", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)

    try:
        live = pull_data(client)
    except Exception:
        print("ERROR: Data pull failed. Leaving live.json untouched.", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)

    LIVE_JSON.write_text(json.dumps(live, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"Wrote {LIVE_JSON} — {len(live['weeks'])} weeks, {len(live['sleep_hrv_14d'])} sleep nights.")


if __name__ == "__main__":
    main()
