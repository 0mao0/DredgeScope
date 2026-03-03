import requests
import datetime
import json

base_url = "http://127.0.0.1:8000"

def test_articles():
    print("\n--- Testing /api/articles ---")
    try:
        r = requests.get(f"{base_url}/api/articles", params={"page": 1, "page_size": 20, "valid": 1, "is_retained": 1})
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"Total: {data.get('total')}")
            print(f"Items: {len(data.get('items', []))}")
            if data.get('items'):
                print(f"First item: {data['items'][0].get('title')}")
        else:
            print(r.text)
    except Exception as e:
        print(f"Error: {e}")

def test_events():
    print("\n--- Testing /api/events ---")
    try:
        now = datetime.datetime.now()
        # Test today's evening report range (08:00 - 18:00)
        # Note: Depending on when this runs, it might be empty if no news today
        # But DB check showed 74 records at 2026-03-03 15:09:52
        
        # Construct range covering 2026-03-03
        start = "2026-03-03T00:00:00"
        end = "2026-03-03T23:59:59"
        
        print(f"Querying {start} to {end}")
        # Default is_retained=1
        r = requests.get(f"{base_url}/api/events", params={"start": start, "end": end})
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            events = data.get('events', [])
            print(f"Count: {len(events)}")
            if events:
                print(f"First event: {events[0].get('title')}")
        else:
            print(r.text)
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_articles()
    test_events()
