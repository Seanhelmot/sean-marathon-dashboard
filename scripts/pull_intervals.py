#!/usr/bin/env python3
"""
pull_intervals.py — Pull training data from intervals.icu and write data/live.json.

On success: overwrites data/live.json with fresh data and exits 0.
On failure: logs the error, leaves data/live.json untouched, exits 1.

Required env vars:
  INTERVALS_API_KEY       — your intervals.icu API key (Settings → API)
  INTERVALS_ATHLETE_ID    — your athlete ID, e.g. "i445042"

Optional env vars (used to supplement gaps):
  GARMIN_EMAIL / GARMIN_PASSWORD — if set, body battery pulled from Garmin as fallback

Install deps:
  pip install requests
"""

import json
import os
import re
import sys
import traceback
from datetime import datetime, timedelta
from pathlib import Path

import requests

REPO_ROOT  = Path(__file__).parent.parent
LIVE_JSON  = REPO_ROOT / "data" / "live.json"
PLAN_JSON  = REPO_ROOT / "data" / "plan.json"

WEEKS_BACK  = 8
SLEEP_DAYS  = 14
BASE_URL    = "https://intervals.icu/api/v1"


# ── API helpers ──────────────────────────────────────────────────────────────

def icu_get(path: str, athlete_id: str, api_key: str, params: dict = None):
    url = f"{BASE_URL}/athlete/{athlete_id}/{path}"
    resp = requests.get(
        url,
        params=params,
        auth=("API_KEY", api_key),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def icu_get_activity(activity_id: str, athlete_id: str, api_key: str):
    """Fetch full detail for a single activity. Returns the activity dict."""
    data = icu_get(f"activities/{activity_id}", athlete_id, api_key)
    if isinstance(data, list):
        return data[0] if data else {}
    return data


def icu_get_laps(activity_id: str, athlete_id: str, api_key: str):
    """Fetch lap splits. Returns list of lap dicts, or None on 404/error."""
    try:
        data = icu_get(f"activities/{activity_id}/laps", athlete_id, api_key)
        return data if isinstance(data, list) else None
    except requests.HTTPError:
        return None
    except Exception:
        return None


# ── Pace / time helpers ──────────────────────────────────────────────────────

def pace_from_speed(speed_m_s: float):
    """m/s → min:sec per km stored as float e.g. 4.35 = 4:35/km"""
    if not speed_m_s or speed_m_s <= 0:
        return None
    min_per_km = 1000 / 60 / speed_m_s
    mins = int(min_per_km)
    secs = round((min_per_km - mins) * 60)
    if secs == 60:
        mins += 1
        secs = 0
    return round(mins + secs / 100, 2)


def pace_from_min_per_km(min_per_km: float):
    """intervals.icu stores pace in secs/m in some fields; this handles min/km directly."""
    if not min_per_km or min_per_km <= 0:
        return None
    mins = int(min_per_km)
    secs = round((min_per_km - mins) * 60)
    return round(mins + secs / 100, 2)


def parse_interval_summary_pace(interval_summary: list) -> float | None:
    """
    Parse quality pace from intervals.icu interval_summary.
    Format: ["12x 4m24s 157bpm", "4x 2m3s 147bpm"]
    The first element is work intervals. Time is per-rep which equals pace/km when
    autolap=1km (true for threshold/tempo). Returns pace as float (4.24 = 4:24/km).
    Returns None if format not recognised.
    """
    if not interval_summary:
        return None
    try:
        m = re.match(r"\d+x\s+(\d+)m(\d+)s", interval_summary[0])
        if not m:
            return None
        mins, secs = int(m.group(1)), int(m.group(2))
        return round(mins + secs / 100, 2)
    except Exception:
        return None


def parse_interval_summary_hr(interval_summary: list) -> int | None:
    """Extract avg HR from the first (work) interval summary entry."""
    if not interval_summary:
        return None
    try:
        m = re.search(r"(\d+)bpm", interval_summary[0])
        return int(m.group(1)) if m else None
    except Exception:
        return None


def iso(d) -> str:
    return d.strftime("%Y-%m-%d")


# ── Long run splits ──────────────────────────────────────────────────────────

def _km_chunks_from_laps(laps: list, chunk_km: int = 5) -> list | None:
    """Aggregate 1km autolaps into 5km chunks for long run breakdown."""
    if not laps:
        return None
    laps = [l for l in laps
            if (l.get("distance") or 0) > 100
            and (l.get("average_heartrate") or l.get("averageHR") or 0) > 80]
    if not laps:
        return None

    chunks, buf, cum = [], [], 0.0
    chunk_m = chunk_km * 1000

    def flush(buf, start_km):
        total_d = sum(l.get("distance") or 0 for l in buf)
        total_t = sum(l.get("elapsed_time") or l.get("moving_time") or 0 for l in buf)
        if total_d < 500 or total_t < 1:
            return None
        avg_hr = sum((l.get("average_heartrate") or l.get("averageHR") or 0) * l.get("distance", 0)
                     for l in buf) / total_d
        spd = total_d / total_t
        end_km = round(start_km + total_d / 1000, 1)
        return {
            "label":   f"{int(start_km)}–{end_km}km",
            "dist_km": round(total_d / 1000, 1),
            "pace":    pace_from_speed(spd),
            "avg_hr":  round(avg_hr),
        }

    for l in laps:
        buf.append(l)
        cum += l.get("distance") or 0
        if cum >= chunk_m - 200:
            c = flush(buf, len(chunks) * chunk_km)
            if c:
                chunks.append(c)
            buf, cum = [], 0.0

    if buf:
        c = flush(buf, len(chunks) * chunk_km)
        if c:
            chunks.append(c)

    return chunks or None


# ── Main pull ────────────────────────────────────────────────────────────────

def pull_data(athlete_id: str, api_key: str):
    from zoneinfo import ZoneInfo
    tz    = ZoneInfo("Australia/Melbourne")
    today = datetime.now(tz).date()
    plan  = json.loads(PLAN_JSON.read_text(encoding="utf-8"))

    build_start_mon = datetime.strptime(plan["build_start_date"], "%Y-%m-%d").date()
    current_week    = max(1, (today - build_start_mon).days // 7 + 1)

    oldest_act = today - timedelta(weeks=WEEKS_BACK)
    oldest_wl  = today - timedelta(days=SLEEP_DAYS - 1)

    # ── Activities list ──────────────────────────────────────────────────────
    acts_raw = icu_get("activities", athlete_id, api_key, params={
        "oldest": iso(oldest_act),
        "newest": iso(today),
    })

    week_buckets: dict[int, dict] = {}
    recent_activities = []

    for act in acts_raw:
        # Skip non-running types
        act_type = (act.get("type") or "").upper()
        if act_type and act_type not in ("RUN", "TRAIL_RUN", "TREADMILL", "VIRTUAL_RUN", ""):
            continue

        start_local_raw = act.get("start_date_local") or act.get("start_date") or ""
        if len(start_local_raw) >= 10:
            act_date = datetime.strptime(start_local_raw[:10], "%Y-%m-%d").date()
        else:
            continue

        start_local_str = start_local_raw[:16] if len(start_local_raw) >= 16 else None

        act_monday = act_date - timedelta(days=act_date.weekday())
        wk_num     = (act_monday - build_start_mon).days // 7 + 1
        if wk_num < 1:
            continue

        dist_m   = act.get("distance") or 0
        dist_km  = dist_m / 1000
        duration = act.get("moving_time") or act.get("elapsed_time") or 0
        avg_hr   = act.get("average_heartrate") or 0
        max_hr   = act.get("max_heartrate") or 0
        speed    = dist_m / duration if duration > 0 else 0  # m/s
        elev     = act.get("total_elevation_gain")
        # intervals.icu cadence is cycles/min (one leg) → ×2 for steps/min
        cadence_raw = act.get("average_cadence")
        cadence  = round(cadence_raw * 2) if cadence_raw else None

        workout_name = (act.get("name") or "").lower()
        act_id = act.get("id") or ""

        # ── Weekly bucket ────────────────────────────────────────────────────
        bucket = week_buckets.setdefault(wk_num, {"actual_km": 0.0, "quality": None, "days": {}})
        bucket["actual_km"] += dist_km

        day_key = iso(act_date)
        existing_day = bucket["days"].get(day_key)
        if existing_day:
            existing_day["dist_km"] = round(existing_day["dist_km"] + dist_km, 1)
        else:
            bucket["days"][day_key] = {
                "dist_km":        round(dist_km, 1),
                "avg_hr":         int(avg_hr) if avg_hr else None,
                "pace":           pace_from_speed(speed),
                "feel":           None,  # filled from detail for recent acts
                "effort":         None,
                "decoupling_pct": None,
                "_main_dist":     dist_km,
            }

        is_quality = avg_hr >= 150 or any(
            kw in workout_name for kw in ("threshold", "interval", "tempo", "track", "repeat", "cruise")
        )

        # ── Recent activities (last 14d) — fetch detail ──────────────────────
        is_recent = act_date >= today - timedelta(days=14)
        if is_recent:
            detail = {}
            if act_id:
                try:
                    detail = icu_get_activity(act_id, athlete_id, api_key)
                except Exception:
                    pass

            feel   = detail.get("feel")           # 1–5 already
            effort = detail.get("perceived_exertion") or detail.get("icu_rpe")
            decouple = detail.get("decoupling")   # % already
            interval_summary = detail.get("interval_summary") or []

            # Weather embedded in activity detail
            wx_temp = detail.get("average_weather_temp")
            wx_wind = detail.get("average_wind_speed")
            wx_dir  = detail.get("prevailing_wind_deg")

            is_long   = dist_km >= 18
            is_qual_r = avg_hr >= 150 or any(
                kw in workout_name for kw in ("threshold", "interval", "tempo", "track", "repeat", "cruise")
            )

            km_chunks_detail = None
            if is_long:
                laps = icu_get_laps(act_id, athlete_id, api_key)
                if laps:
                    km_chunks_detail = _km_chunks_from_laps(laps)

            entry = {
                "date":            iso(act_date),
                "start_local":     start_local_str,
                "name":            act.get("name") or "Run",
                "dist_km":         round(dist_km, 2),
                "duration_s":      int(duration),
                "avg_hr":          int(avg_hr) if avg_hr else None,
                "max_hr":          int(max_hr) if max_hr else None,
                "pace":            pace_from_speed(speed),
                "feel":            int(feel) if feel is not None else None,
                "effort":          float(effort) if effort is not None else None,
                "elevation_gain":  elev,
                "avg_cadence":     cadence,
            }
            if decouple is not None:
                entry["decoupling_pct"] = round(float(decouple), 1)
            if interval_summary:
                entry["interval_summary"] = interval_summary
            if km_chunks_detail:
                entry["km_chunks"] = km_chunks_detail
            if wx_temp is not None:
                entry["wx_temp_c"]  = round(wx_temp, 1)
                entry["wx_wind_kph"] = round(wx_wind, 1) if wx_wind else None
                entry["wx_wind_dir"] = int(wx_dir) if wx_dir is not None else None

            # Update the day entry with feel/effort/decoupling from detail
            if day_key in bucket["days"]:
                d = bucket["days"][day_key]
                if feel   is not None: d["feel"]           = int(feel)
                if effort is not None: d["effort"]         = float(effort)
                if decouple is not None: d["decoupling_pct"] = round(float(decouple), 1)

            recent_activities.append(entry)

        # ── Quality session — weekly bucket ──────────────────────────────────
        if is_quality and bucket["quality"] is None:
            if is_recent and interval_summary:
                q_pace = parse_interval_summary_pace(interval_summary)
                q_hr   = parse_interval_summary_hr(interval_summary)
            else:
                q_pace = None
                q_hr   = None
            bucket["quality"] = {
                "pace_min_per_km":    q_pace if q_pace else pace_from_speed(speed),
                "avg_hr":             q_hr   if q_hr   else int(avg_hr),
                "work_intervals_only": q_pace is not None,
            }

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

    # ── Wellness ─────────────────────────────────────────────────────────────
    wellness_raw = icu_get("wellness", athlete_id, api_key, params={
        "oldest": iso(oldest_wl),
        "newest": iso(today),
    })
    # Wellness returns list sorted oldest→newest
    wellness_by_date = {w["id"]: w for w in wellness_raw} if isinstance(wellness_raw, list) else {}

    today_wl   = wellness_by_date.get(iso(today)) or {}
    rhr        = today_wl.get("restingHR")
    hrv_today  = today_wl.get("hrv")
    sleep_score = today_wl.get("sleepScore")
    sleep_secs  = today_wl.get("sleepSecs") or 0
    sleep_hrs   = round(sleep_secs / 3600, 1) if sleep_secs else None
    ctl         = today_wl.get("ctl")
    atl         = today_wl.get("atl")
    vo2max      = today_wl.get("vo2max")

    # HRV 7d average
    hrv_values = [
        wellness_by_date.get(iso(today - timedelta(days=i)), {}).get("hrv")
        for i in range(7)
    ]
    hrv_values = [v for v in hrv_values if v is not None]
    hrv_7d_avg = round(sum(hrv_values) / len(hrv_values)) if hrv_values else None

    # Sleep + HRV 14d
    sleep_hrv_14d = []
    for offset in range(SLEEP_DAYS - 1, -1, -1):
        night = today - timedelta(days=offset)
        wl    = wellness_by_date.get(iso(night))
        if not wl:
            continue
        sc      = wl.get("sleepScore")
        hrv_n   = wl.get("hrv")
        rhr_n   = wl.get("restingHR")
        if sc is not None or hrv_n is not None or rhr_n is not None:
            sleep_hrv_14d.append({
                "date":  iso(night),
                "score": sc,
                "hrv":   hrv_n,
                "rhr":   rhr_n,
            })

    # Body battery — Garmin-only; try to pull if credentials available
    body_battery = None
    garmin_email    = os.environ.get("GARMIN_EMAIL", "").strip()
    garmin_password = os.environ.get("GARMIN_PASSWORD", "").strip()
    if garmin_email and garmin_password:
        try:
            from garminconnect import Garmin
            g = Garmin(garmin_email, garmin_password)
            g.login()
            bb = g.get_body_battery(iso(today), iso(today))
            if bb and isinstance(bb, list):
                entries = bb[0].get("bodyBatteryValuesArray") or []
                if entries:
                    body_battery = max(v[1] for v in entries if v[1] is not None)
        except Exception:
            pass

    # Preserve this_week_days from existing live.json
    this_week_days = None
    try:
        existing = json.loads(LIVE_JSON.read_text(encoding="utf-8"))
        this_week_days = existing.get("this_week_days")
    except Exception:
        pass

    from zoneinfo import ZoneInfo
    return {
        "generated_at":   datetime.now(ZoneInfo("Australia/Melbourne")).strftime("%Y-%m-%dT%H:%M:%S+10:00"),
        "current_week":   current_week,
        "today": {
            "rhr":           rhr,
            "hrv_7d_avg":    hrv_7d_avg,
            "hrv_status":    None,           # not available in intervals.icu
            "sleep_score":   sleep_score,
            "sleep_hrs":     sleep_hrs,
            "body_battery":  body_battery,
            "vo2max_garmin": round(vo2max) if vo2max else None,
            "vo2max_note":   "lab-tested 58.4 (2022)",
            "ctl":           round(ctl, 1) if ctl else None,
            "atl":           round(atl, 1) if atl else None,
        },
        "this_week_days":    this_week_days,
        "weeks":             weeks_out,
        "sleep_hrv_14d":     sleep_hrv_14d,
        "recent_activities": recent_activities,
    }


def main():
    athlete_id = os.environ.get("INTERVALS_ATHLETE_ID", "").strip()
    api_key    = os.environ.get("INTERVALS_API_KEY", "").strip()

    if not athlete_id or not api_key:
        print("ERROR: INTERVALS_ATHLETE_ID and INTERVALS_API_KEY env vars must be set.", file=sys.stderr)
        sys.exit(1)

    print(f"Pulling data for athlete {athlete_id} from intervals.icu…")

    try:
        live = pull_data(athlete_id, api_key)
    except Exception:
        print("ERROR: Data pull failed. Leaving live.json untouched.", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)

    LIVE_JSON.write_text(json.dumps(live, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {LIVE_JSON} — {len(live['weeks'])} weeks, {len(live['sleep_hrv_14d'])} sleep nights.")


if __name__ == "__main__":
    main()
