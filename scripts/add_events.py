"""
Add new events from CSV to Supabase, skipping duplicates.
Usage: python scripts/add_events.py
"""
import os
import sys
import csv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from supabase import create_client

url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_KEY')

if not url or not key:
    print("ERROR: SUPABASE_URL and SUPABASE_KEY must be set in .env")
    sys.exit(1)

sb = create_client(url, key)

# --- Load events from CSV ---
csv_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'sample_events.csv')
with open(csv_path, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    csv_events = [row for row in reader if row.get('name', '').strip()]

print(f"Loaded {len(csv_events)} events from CSV")

# --- Get existing event names from Supabase ---
existing = sb.table('events').select('name').execute()
existing_names = {e['name'] for e in existing.data}
print(f"Found {len(existing_names)} existing events in database")

# --- Determine which events to insert ---
to_insert = []
skipped = []

for event in csv_events:
    name = event['name'].strip()
    if name in existing_names:
        skipped.append(name)
    else:
        to_insert.append({
            'name': name,
            'industry': event['industry'].strip(),
            'start_date': event['start_date'].strip(),
            'end_date': event['end_date'].strip(),
            'location': event['location'].strip(),
            'country': event['country'].strip(),
            'website': event['website'].strip(),
            'description': event['description'].strip(),
        })

# --- Insert new events ---
if to_insert:
    result = sb.table('events').insert(to_insert).execute()
    print(f"\nInserted {len(result.data)} new events:")
    for e in result.data:
        print(f"  + {e['name']} ({e['industry']}, {e['start_date']})")
else:
    print("\nNo new events to insert — all already exist.")

if skipped:
    print(f"\nSkipped {len(skipped)} existing events:")
    for name in skipped:
        print(f"  - {name}")

print("\nDone!")
