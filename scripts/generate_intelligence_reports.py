"""
Generate intelligence reports for all 4 verticals.
Creates 8 reports total: 4 current + 4 backdated to mid-February 2026.
Calls Perplexity API directly (bypasses Flask auth).
Usage: python scripts/generate_intelligence_reports.py
"""
import os
import sys
import time
from datetime import date, datetime

# Add parent directory to path so we can import services
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from supabase import create_client
from services.perplexity_service import generate_intelligence_report

url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_KEY')
sb = create_client(url, key)

VERTICALS = ['aerospace', 'automotive', 'robotics', 'ai_electronics']
BACKDATE_TIMESTAMP = '2026-02-15T10:00:00Z'


def check_existing_reports():
    """Fetch existing reports to avoid duplicates."""
    result = sb.table('intelligence_reports').select('vertical, created_at').execute()
    existing = set()
    for r in result.data:
        # Track by vertical + date (just the date part)
        created = r['created_at'][:10] if r.get('created_at') else ''
        existing.add((r['vertical'], created))
    return existing


def generate_and_store(vertical, as_of_date=None, created_at=None):
    """Generate a report and insert it into Supabase."""
    label = f"{vertical}" + (f" (as of {as_of_date})" if as_of_date else " (current)")
    print(f"  Generating report for {label}...", flush=True)

    result = generate_intelligence_report(vertical, as_of_date=as_of_date)

    if not result['success']:
        print(f"  FAILED - {result['error']}", flush=True)
        return False

    row = {
        'vertical': vertical,
        'report_html': result['report_html'],
        'top_3_json': result['top_3_json'],
    }
    if created_at:
        row['created_at'] = created_at

    sb.table('intelligence_reports').insert(row).execute()
    top_count = len(result['top_3_json']) if isinstance(result['top_3_json'], list) else 0
    print(f"  OK - Report stored ({top_count} top headlines)", flush=True)
    return True


def main():
    existing = check_existing_reports()
    today_str = date.today().isoformat()
    backdate_str = BACKDATE_TIMESTAMP[:10]

    success = 0
    skipped = 0
    failed = 0
    total = len(VERTICALS) * 2

    print(f"Intelligence Report Generation")
    print(f"{'='*50}")
    print(f"Verticals: {', '.join(VERTICALS)}")
    print(f"Reports to generate: {total} (4 current + 4 backdated to {backdate_str})")
    print(f"{'='*50}")

    # --- Current reports ---
    print(f"\n--- Current Reports ({today_str}) ---")
    for i, vertical in enumerate(VERTICALS):
        if (vertical, today_str) in existing:
            print(f"  SKIP - {vertical}: report already exists for {today_str}", flush=True)
            skipped += 1
            continue

        if generate_and_store(vertical):
            success += 1
        else:
            failed += 1

        # Rate limit between API call pairs
        if i < len(VERTICALS) - 1:
            print(f"  (waiting 3s for rate limit...)", flush=True)
            time.sleep(3)

    # --- Backdated reports ---
    print(f"\n--- Backdated Reports ({backdate_str}) ---")
    for i, vertical in enumerate(VERTICALS):
        if (vertical, backdate_str) in existing:
            print(f"  SKIP - {vertical}: report already exists for {backdate_str}", flush=True)
            skipped += 1
            continue

        if generate_and_store(vertical, as_of_date='mid-February 2026', created_at=BACKDATE_TIMESTAMP):
            success += 1
        else:
            failed += 1

        # Rate limit between API call pairs
        if i < len(VERTICALS) - 1:
            print(f"  (waiting 3s for rate limit...)", flush=True)
            time.sleep(3)

    print(f"\n{'='*50}")
    print(f"Done! Success: {success}, Skipped: {skipped}, Failed: {failed} (out of {total})")


if __name__ == '__main__':
    main()
