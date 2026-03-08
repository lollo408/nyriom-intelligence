"""
Delete all existing intelligence reports and regenerate with top-5 format.
Usage: python scripts/delete_and_regenerate_reports.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from supabase import create_client

url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_KEY')
sb = create_client(url, key)

# Fetch existing reports
existing = sb.table('intelligence_reports').select('id, vertical, created_at').execute()
print(f"Found {len(existing.data)} existing reports:")
for r in existing.data:
    print(f"  - {r['vertical']} ({r['created_at'][:10]}) id={r['id']}")

if not existing.data:
    print("Nothing to delete.")
    sys.exit(0)

# Delete all
for r in existing.data:
    sb.table('intelligence_reports').delete().eq('id', r['id']).execute()
    print(f"  Deleted {r['vertical']} ({r['created_at'][:10]})")

print(f"\nAll {len(existing.data)} reports deleted.")
print("Now run: python scripts/generate_intelligence_reports.py")
