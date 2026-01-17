import requests
import json
import os
import random
import string
from datetime import datetime, timedelta

# --- CONFIGURATION ---
FEATURED_TEAMS = [
    "al-nassr", "inter miami cf", "fc-bayern-munchen", "dortmund", "leverkusen", 
    "paris-saint-germain", "juventus", "atletico-madrid", "barcelona", "real madrid", 
    "arsenal", "chelsea", "manchester city", "manchester united", "liverpool",
    "portugal", "argentina", "brazil", "spain", "england", "france", "inter", "milan"
]

# Using the specialized API subdomain which is more reliable for events
API_BASE = "https://api.sofascore.com/api/v1"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Origin': 'https://www.sofascore.com',
    'Referer': 'https://www.sofascore.com/'
}

def generate_custom_id():
    letters = ''.join(random.choices(string.ascii_lowercase, k=4))
    numbers = ''.join(random.choices(string.digits, k=6))
    return f"{letters}{numbers}"

def clean_team_name(name):
    return name.replace('-', ' ').replace('FC', '').replace('fc', '').strip()

def get_matches(date_str):
    print(f"🔍 Fetching matches for: {date_str}")
    url = f"{API_BASE}/sport/football/scheduled-events/{date_str}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            return response.json().get('events', [])
        else:
            print(f"⚠️ API Error {response.status_code} for date {date_str}")
            return []
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return []

def get_highlights(event_id):
    url = f"{API_BASE}/event/{event_id}/highlights"
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            return response.json().get('highlights', [])
        return []
    except:
        return []

def main():
    # Get Yesterday and Today
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    
    dates_to_check = [
        yesterday.strftime('%Y-%m-%d'),
        today.strftime('%Y-%m-%d')
    ]

    all_highlights = []
    seen_match_ids = set()

    for date_str in dates_to_check:
        events = get_matches(date_str)
        
        # Filter for Finished matches
        finished_matches = [e for e in events if e.get('status', {}).get('type') in ['finished', 'ended']]
        
        for match in finished_matches:
            match_id = match.get('id')
            if match_id in seen_match_ids:
                continue
            seen_match_ids.add(match_id)

            home_name = match.get('homeTeam', {}).get('name', '').lower()
            away_name = match.get('awayTeam', {}).get('name', '').lower()
            
            # Check priority
            is_priority = any(team in home_name or team in away_name for team in FEATURED_TEAMS)

            highlights_data = get_highlights(match_id)
            if highlights_data:
                yt_link = None
                for h in highlights_data:
                    subtitle = h.get('subtitle', '').lower()
                    # Look for highlights or extended coverage
                    if "highlights" in subtitle or "extended" in subtitle:
                        url = h.get('url', '') or h.get('sourceUrl', '')
                        if 'youtube.com' in url or 'youtu.be' in url:
                            yt_link = url
                            break
                
                if yt_link:
                    all_highlights.append({
                        "id": generate_custom_id(),
                        "team1": clean_team_name(match['homeTeam']['name']),
                        "team2": clean_team_name(match['awayTeam']['name']),
                        "category": match.get('tournament', {}).get('name', 'Football'),
                        "date": datetime.fromtimestamp(match['startTimestamp']).strftime('%Y-%m-%d'),
                        "link": yt_link,
                        "isPriority": is_priority
                    })

    if not all_highlights:
        print("Empty queue: No highlights found with YouTube links.")
        return

    # --- THE SORTING LOGIC ---
    # Sorts by Priority (True first) then by Date (Newest first)
    all_highlights.sort(key=lambda x: (x['isPriority'], x['date']), reverse=True)

    # Save to api/highlights.json
    os.makedirs('api', exist_ok=True)
    with open('api/highlights.json', 'w', encoding='utf-8') as f:
        json.dump(all_highlights, f, indent=2, ensure_ascii=False)

    print(f"🏁 Success! Created api/highlights.json with {len(all_highlights)} items.")
    print(f"🔥 Priority matches included: {sum(1 for x in all_highlights if x['isPriority'])}")

if __name__ == "__main__":
    main()
