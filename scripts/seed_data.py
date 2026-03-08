"""
Seed script: Wipe and re-seed Nyriom industry events from CSV.
Usage: python scripts/seed_data.py
"""
import os
import sys
import csv
from dotenv import load_dotenv

# Load env from project root
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from supabase import create_client

url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_KEY')

if not url or not key:
    print("ERROR: SUPABASE_URL and SUPABASE_KEY must be set in .env")
    sys.exit(1)

supabase = create_client(url, key)

# --- Step 1: Wipe existing data (FK-safe order) ---
print("Wiping existing data...")
for table in ['event_summaries', 'intelligence_reports', 'user_preferences', 'events']:
    try:
        # Delete all rows (neq filter on id to match everything)
        supabase.table(table).delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()
        print(f"  Cleared {table}")
    except Exception as e:
        print(f"  Warning: {table} - {e}")

# --- Step 2: Reset app_config ---
print("Resetting app_config...")
try:
    supabase.table('app_config').upsert({
        'key': 'maintenance_mode',
        'value': {'enabled': False, 'message': ''}
    }).execute()
    supabase.table('app_config').upsert({
        'key': 'app_version',
        'value': {'version': '1.0.0', 'min_version': '1.0.0'}
    }).execute()
    print("  app_config reset OK")
except Exception as e:
    print(f"  Warning: app_config - {e}")

# --- Step 3: Seed events from CSV ---
csv_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'sample_events.csv')
print(f"Reading events from {csv_path}...")

events = []
with open(csv_path, 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        event = {
            'name': row['name'].strip(),
            'industry': row['industry'].strip(),
            'start_date': row['start_date'].strip(),
            'location': row.get('location', '').strip() or None,
            'country': row.get('country', '').strip() or None,
            'website': row.get('website', '').strip() or None,
            'description': row.get('description', '').strip() or None,
        }
        end_date = row.get('end_date', '').strip()
        if end_date:
            event['end_date'] = end_date
        events.append(event)

print(f"Inserting {len(events)} events...")
result = supabase.table('events').insert(events).execute()
print(f"  Inserted {len(result.data)} events successfully!")

# Print summary
from collections import Counter
industries = Counter(e['industry'] for e in events)
print("\nSummary by industry:")
for industry, count in sorted(industries.items()):
    print(f"  {industry}: {count}")

print("\nDone! Maintenance mode is OFF, app is ready.")
