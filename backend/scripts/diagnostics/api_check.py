import requests
import json

try:
    print("Fetching jobs...")
    r = requests.get("http://localhost/api/v1/jobs/?ingestion_type=link_reconstruction")
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        jobs = r.json()
        print(f"Found {len(jobs)} jobs")
        for j in jobs:
            print(f"ID: {j['id']}, Status: {j['status']}, Type: {j['ingestion_type']}")
    else:
        print(f"Error: {r.text}")
except Exception as e:
    print(f"Connection failed: {e}")
