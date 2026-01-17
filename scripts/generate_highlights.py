import asyncio
import json
import os
import random
import string
from datetime import datetime, timedelta
from curl_cffi.requests import AsyncSession

# --- CONFIGURATION ---
FEATURED_TEAMS = [
    "al-nassr", "inter miami cf", "fc-bayern-munchen", "dortmund", "leverkusen", 
    "paris-saint-germain", "juventus", "atletico-madrid", "barcelona", "real madrid", 
    "arsenal", "chelsea", "manchester city", "manchester united", "liverpool",
    "portugal", "argentina", "brazil", "spain", "england", "france", "inter", "milan", "roma"
]

API_BASE = "https://api.sofascore.com/api/v1"

def generate_custom_id():
    letters = ''.join(random.choices(string.ascii_lowercase, k=4))
    numbers = ''.join(random.choices(string.digits, k=6))
    return f"{letters}{numbers}"

def clean_team_name(name):
    return name.replace('-', ' ').replace('FC', '').replace('fc', '').strip()

async def get_matches(session, date_str):
    """Fetches matches for a specific date using browser impersonation."""
    url = f"{API_BASE}/sport/football/scheduled-events/{date_str}"
    print(f"🔍 Fetching matches for: {date_str}")
    try:
        res = await session.get(url, impersonate="chrome120", timeout=15)
        if res.status_code == 200:
            return res.json().get('events', [])
        print(f"⚠️ API Error {res.status_code} for date {date_str}")
    except Exception as e:
        print(f"❌ Error fetching {date_str}: {e}")
    return []

async def get_highlight_data(session, event_id):
    """Fetches highlight links for a specific match ID."""
    url = f"{API_BASE}/event/{event_id}/highlights"
    try:
        res = await session.get(url, impersonate="chrome120", timeout=10)
        if res.status_code == 200:
            return res.json().get('highlights', [])
    except:
        pass
    return []

async def process_match(session, match, today_str):
    """Processes a single match to find YouTube highlights."""
    match_id = match.get('id')
    home_name = match.get('homeTeam', {}).get('name', '').lower()
    away_name = match.get('awayTeam', {}).get('name', '').lower()
    
    # Check if match involves a Priority Team
    is_priority = any(team in home_name or team in away_name for team in FEATURED_TEAMS)
    
    highlights = await get_highlight_data(session, match_id)
    if not highlights:
        return None

    yt_link = None
    for h in highlights:
        subtitle = h.get('subtitle', '').lower()
        # Filter for quality highlights
        if "highlights" in subtitle or "extended" in subtitle:
            url = h.get('url', '') or h.get('sourceUrl', '')
            if 'youtube.com' in url or 'youtu.be' in url:
                yt_link = url
                break
    
    if yt_link:
        return {
            "id": generate_custom_id(),
            "team1": clean_team_name(match['homeTeam']['name']),
            "team2": clean_team_name(match['awayTeam']['name']),
            "category": match.get('tournament', {}).get('name', 'Football'),
            "date": datetime.fromtimestamp(match['startTimestamp']).strftime('%Y-%m-%d'),
            "link": yt_link,
            "isPriority": is_priority
        }
    return None

async def main():
    async with AsyncSession() as session:
        # Check Yesterday and Today to catch late-night games
        now = datetime.now()
        dates_to_check = [
            (now - timedelta(days=1)).strftime('%Y-%m-%d'),
            now.strftime('%Y-%m-%d')
        ]

        all_events = []
        for date_str in dates_to_check:
            events = await get_matches(session, date_str)
            all_events.extend(events)

        # Filter for Finished matches
        finished_matches = [e for e in all_events if e.get('status', {}).get('type') in ['finished', 'ended']]
        print(f"✅ Found {len(finished_matches)} finished matches to check.")

        # Process highlights in batches to be respectful
        results = []
        batch_size = 10
        for i in range(0, len(finished_matches), batch_size):
            batch = finished_matches[i:i+batch_size]
            tasks = [process_match(session, m, dates_to_check[1]) for m in batch]
            batch_results = await asyncio.gather(*tasks)
            results.extend([r for r in batch_results if r])
            await asyncio.sleep(1) # Small delay to avoid rate limiting

        if not results:
            print("📭 No highlights found today.")
            return

        # --- SORTING LOGIC: Priority Teams first, then Newest Date ---
        results.sort(key=lambda x: (x['isPriority'], x['date']), reverse=True)

        # Save to api/highlights.json
        os.makedirs('api', exist_ok=True)
        with open('api/highlights.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"🏁 Success! Created api/highlights.json with {len(results)} items.")
        print(f"🔥 Priority matches at top: {sum(1 for x in results if x['isPriority'])}")

if __name__ == "__main__":
    asyncio.run(main())
