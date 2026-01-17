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
FILE_PATH = 'api/highlights.json'

def generate_custom_id():
    return ''.join(random.choices(string.ascii_lowercase, k=4)) + ''.join(random.choices(string.digits, k=6))

def clean_team_name(name):
    return name.replace('-', ' ').replace('FC', '').replace('fc', '').strip()

async def get_matches(session, date_str):
    url = f"{API_BASE}/sport/football/scheduled-events/{date_str}"
    try:
        res = await session.get(url, impersonate="chrome120", timeout=15)
        if res.status_code == 200: return res.json().get('events', [])
    except: pass
    return []

async def get_highlight_data(session, event_id):
    url = f"{API_BASE}/event/{event_id}/highlights"
    try:
        res = await session.get(url, impersonate="chrome120", timeout=10)
        if res.status_code == 200: return res.json().get('highlights', [])
    except: pass
    return []

async def process_match(session, match):
    match_id = match.get('id')
    home_name = match.get('homeTeam', {}).get('name', '').lower()
    away_name = match.get('awayTeam', {}).get('name', '').lower()
    
    # Check priority for new matches
    is_priority = any(team in home_name or team in away_name for team in FEATURED_TEAMS)
    
    highlights = await get_highlight_data(session, match_id)
    if not highlights: return None

    yt_link = None
    for h in highlights:
        subtitle = h.get('subtitle', '').lower()
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
    # 1. LOAD EXISTING DATA (2025 + 2026)
    existing_data = []
    if os.path.exists(FILE_PATH):
        try:
            with open(FILE_PATH, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
                if not isinstance(existing_data, list): existing_data = []
        except: 
            print("⚠️ Could not read existing file, starting fresh.")
            existing_data = []

    async with AsyncSession() as session:
        # Check Today and Yesterday
        now = datetime.now()
        dates = [(now - timedelta(days=1)).strftime('%Y-%m-%d'), now.strftime('%Y-%m-%d')]
        
        all_events = []
        for d in dates: 
            all_events.extend(await get_matches(session, d))

        finished = [e for e in all_events if e.get('status', {}).get('type') in ['finished', 'ended']]
        
        # 2. FETCH NEW HIGHLIGHTS
        new_highlights = []
        batch_size = 10
        for i in range(0, len(finished), batch_size):
            tasks = [process_match(session, m) for m in finished[i:i+batch_size]]
            batch_res = await asyncio.gather(*tasks)
            new_highlights.extend([r for r in batch_res if r])
            await asyncio.sleep(1)

        # 3. MERGE & DEDUPLICATE (Keep ALL data)
        combined = new_highlights + existing_data
        unique_list = []
        seen_links = set()
        
        for item in combined:
            link = item.get('link')
            if link and link not in seen_links:
                # Update priority for old entries if missing
                if 'isPriority' not in item:
                    t1, t2 = item.get('team1', '').lower(), item.get('team2', '').lower()
                    item['isPriority'] = any(t in t1 or t in t2 for t in FEATURED_TEAMS)
                
                unique_list.append(item)
                seen_links.add(link)

        # 4. SORT (Priority First, then Date)
        unique_list.sort(
            key=lambda x: (
                x.get('isPriority', False), 
                x.get('date', '1970-01-01')
            ), 
            reverse=True
        )

        # 5. SAVE EVERYTHING (No limit or very high limit like 5000)
        final_list = unique_list[:5000] 

        os.makedirs('api', exist_ok=True)
        with open(FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(final_list, f, indent=2, ensure_ascii=False)

        print(f"🏁 Success! API now has {len(final_list)} items total.")

if __name__ == "__main__":
    asyncio.run(main())
