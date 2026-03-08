"""
Generate AI summaries for all past events without summaries.
Calls Perplexity API directly (bypasses Flask auth).
Usage: python scripts/generate_summaries.py
"""
import os
import sys
import time

# Add parent directory to path so we can import services
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from supabase import create_client
from services.perplexity_service import generate_event_summary

url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_KEY')
sb = create_client(url, key)

# Get all past events
from datetime import date
events = sb.table('events').select('*').order('start_date').execute()
today = date.today().isoformat()
past = [e for e in events.data if (e.get('end_date') or e['start_date']) < today]

# Get existing completed summaries
summaries = sb.table('event_summaries').select('event_id').eq('status', 'completed').execute()
existing = {s['event_id'] for s in summaries.data}

# Filter to events without summaries
to_generate = [e for e in past if e['id'] not in existing]
print(f"Found {len(to_generate)} past events without summaries (out of {len(past)} total)")

if not to_generate:
    print("All past events already have summaries!")
    sys.exit(0)

success = 0
failed = 0

for i, event in enumerate(to_generate):
    print(f"\n[{i+1}/{len(to_generate)}] {event['name']} ({event.get('industry', 'General')})...", flush=True)
    try:
        result = generate_event_summary(
            event_name=event['name'],
            event_date=event.get('end_date') or event['start_date'],
            industry=event.get('industry', 'General'),
            location=event.get('location', 'Unknown'),
            website=event.get('website')
        )

        if result['success']:
            # Store in Supabase
            sb.table('event_summaries').upsert({
                'event_id': event['id'],
                'summary_text': result['summary'],
                'status': 'completed'
            }, on_conflict='event_id').execute()
            print(f"  OK - Summary generated and stored", flush=True)
            success += 1
        else:
            print(f"  FAILED - {result['error']}", flush=True)
            failed += 1
    except Exception as e:
        print(f"  ERROR - {e}", flush=True)
        failed += 1

    # Brief pause between requests
    if i < len(to_generate) - 1:
        time.sleep(2)

print(f"\n{'='*50}")
print(f"Done! Success: {success}, Failed: {failed}")
