import requests, json
from datetime import date

AUTH = ('API_KEY', '6123b5w739ctaytjstmw7kmn6')
BASE = 'https://intervals.icu/api/v1/athlete'

athletes = [
    ('i620570', 'Chess'),
    ('i619779', 'Drakes'),
    ('i620736', 'Rohan Cooper'),
]

for aid, label in athletes:
    profile = requests.get(f'{BASE}/{aid}', auth=AUTH, timeout=20).json()
    print(f'=== {label} ({aid}) ===')
    print(f'  name: {profile.get("name")}')
    ss = profile.get('sportSettings') or []
    run = next((s for s in ss if 'Run' in (s.get('types') or [])), None)
    if run:
        print(f'  max_hr={run.get("max_hr")}  lthr={run.get("lthr")}  thresh_pace={run.get("threshold_pace")}')

    wl = requests.get(f'{BASE}/{aid}/wellness', auth=AUTH,
        params={'oldest': str(date.today()), 'newest': str(date.today())}, timeout=20).json()
    if wl and isinstance(wl, list) and wl:
        w = wl[0]
        print(f'  CTL:{w.get("ctl")}  ATL:{w.get("atl")}  HRV:{w.get("hrv")}  RHR:{w.get("restingHR")}')

    acts = requests.get(f'{BASE}/{aid}/activities', auth=AUTH,
        params={'oldest': str(date.today().replace(day=1)), 'newest': str(date.today())}, timeout=20).json()
    runs = [a for a in (acts or []) if 'RUN' in (a.get('type') or '').upper() or a.get('type') == 'Run']
    print(f'  runs this month: {len(runs)}')
    for a in runs[:3]:
        d = (a.get('start_date_local') or '')[:10]
        dist = round((a.get('distance') or 0)/1000, 1)
        print(f'    {d}  {a.get("name","")}  {dist}km  HR:{a.get("average_heartrate")}')
    print()
