#!/usr/bin/env python3
"""
Push MSR Theme of the Week note to all athletes on intervals.icu.

Pre-scheduled themes run W7 Jun 30 through W22 Oct 13.
Each Monday at 06:00 local time, the same note lands on every athlete's calendar.

Usage (manual override):
    python scripts/push_weekly_theme.py "Your custom theme text"
"""
import requests, os, sys

AUTH = ('API_KEY', os.environ.get('INTERVALS_API_KEY', '6123b5w739ctaytjstmw7kmn6'))
BASE = 'https://intervals.icu/api/v1/athlete'

ATHLETES = [
    'i445042',  # Sean Helmot
    'i620475',  # Stacey Harfield
    'i620570',  # Chess
    'i619779',  # Drakes
    'i620736',  # Rohan Cooper
    'i625671',  # Aidan Burrell
]

THEMES = [
    ('2026-06-29', "Each week we'll focus on one area of athlete lifestyle that compounds your training. Small habits, big results. Pay attention this week — what area of your life as an athlete needs the most work?"),
    ('2026-07-06', "SLEEP — 8hrs minimum. Phone off 9:30pm. No screens in bed. This week track your sleep score daily and notice how it correlates with your training quality."),
    ('2026-07-13', "HYDRATION — 2.5L daily minimum. Start every run already hydrated. Urine should be pale yellow by mid-morning. Dehydration kills performance before you even notice it."),
    ('2026-07-20', "EASY DAY DISCIPLINE — If your easy run feels too easy, you've got it right. Easy days are where your aerobic base is built. Rushing them steals from Sunday."),
    ('2026-07-27', "NUTRITION TIMING — Eat within 30 minutes of every run. Prioritise protein first. Your body repairs while you sleep — give it the materials to work with."),
    ('2026-08-03', "RESET — Lakeside is done. Reflect on what it showed you. Recalibrate your effort levels. Recommit to the process. The real work starts now."),
    ('2026-08-10', "CONSISTENCY — The athletes who improve most are not the most talented — they are the most consistent. Show up on the hard days. That is where fitness is built."),
    ('2026-08-17', "RUNNING FORM — Tall posture. Relaxed shoulders. Hands loose. Aim for 180 cadence. Film yourself from behind this week and notice what you see."),
    ('2026-08-24', "GUT TRAINING — Your gut is trainable. Practise race nutrition on every long run this week. Same gels, same timing as race day. No surprises in October."),
    ('2026-08-31', "STRESS MANAGEMENT — Life stress and training stress draw from the same recovery pool. Protect your sleep and downtime this week like it is a training session."),
    ('2026-09-07', "ALCOHOL — Zero this week. Notice how your HRV, sleep score and morning energy respond. Compare the data honestly. You might be surprised."),
    ('2026-09-14', "MENTAL TOUGHNESS — When it gets hard in training, get curious not anxious. Ask what your body is telling you. Discomfort is information, not a threat."),
    ('2026-09-21', "RECOVERY — Foam roll for 10 minutes daily. Legs up the wall for 10 minutes after every run. Sleep is still the most powerful recovery tool you have."),
    ('2026-09-28', "RACE NUTRITION — Lock in your gel strategy this week. Write it down. Practise it on Sunday. Know your split targets. Preparation removes race day anxiety."),
    ('2026-10-05', "CONFIDENCE — You have done the work. Every early morning, every hard session, every disciplined easy run has compounded. Trust what you have built. Go execute."),
    ('2026-10-13', "REFLECT AND RESET — What did this block teach you about yourself as an athlete? Write it down. That insight is the foundation of your next build."),
]

TITLE = 'MSR STRIVE FOR EXCELLENCE — THEME OF THE WEEK'


def push_theme(date_str, description):
    event = {
        'start_date_local': f'{date_str}T06:00:00',
        'name':             TITLE,
        'type':             'Note',
        'category':         'NOTE',
        'description':      description,
    }
    results = []
    for aid in ATHLETES:
        r = requests.post(f'{BASE}/{aid}/events', auth=AUTH, json=event, timeout=15)
        ok = r.status_code in (200, 201)
        results.append((aid, ok, r.status_code))
        status = 'OK' if ok else f'FAIL {r.status_code}'
        print(f'  {status}  {aid}  {date_str}')
    return results


def main():
    if len(sys.argv) > 1:
        # Manual override: push custom text to next Monday
        from datetime import date, timedelta
        today = date.today()
        days_ahead = (0 - today.weekday()) % 7 or 7
        next_monday = today + timedelta(days=days_ahead)
        text = ' '.join(sys.argv[1:])
        print(f'Pushing custom theme to {next_monday}…')
        push_theme(str(next_monday), text)
    else:
        # Push all pre-scheduled themes
        print(f'Pushing {len(THEMES)} weekly themes to {len(ATHLETES)} athletes…')
        for date_str, text in THEMES:
            print(f'\n{date_str}:')
            push_theme(date_str, text)
        print('\nDone.')


if __name__ == '__main__':
    main()
