import sys
import os
import requests
import json
from dotenv import load_dotenv

# Force UTF-8 encoding for stdout
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

load_dotenv()

def inspect_group(group_id):
    cookie = os.getenv("ZSXQ_COOKIE")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Cookie': cookie,
        'Referer': 'https://wx.zsxq.com/',
        'Accept': 'application/json, text/plain, */*'
    }
    
    # 1. Get Group Info
    print(f"--- Fetching Group Info for {group_id} ---")
    group_url = f"https://api.zsxq.com/v2/groups/{group_id}"
    resp = requests.get(group_url, headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        print(json.dumps(data, indent=2, ensure_ascii=False))
        
        # Check if topics are mentioned
        resp_data = data.get('resp', {})
        group_info = resp_data.get('group', {})
        print(f"\nGroup Name: {group_info.get('name')}")
        print(f"Group Type: {group_info.get('type')}")
    else:
        print(f"Failed to fetch group info: {resp.status_code}")
        print(resp.text)

    # 2. Try Columns List if separate
    print(f"\n--- Checking Columns ---")
    columns_url = f"https://api.zsxq.com/v2/groups/{group_id}/columns"
    resp = requests.get(columns_url, headers=headers)
    if resp.status_code == 200:
        print("Columns Metadata:")
        print(json.dumps(resp.json(), indent=2, ensure_ascii=False))
    else:
        print(f"Columns endpoint (groups/id/columns) returned: {resp.status_code}")

    # 3. Try Root Columns if standard
    print(f"\n--- Checking Root Columns (v2/columns) ---")
    # Sometimes it's v2/columns?group_id=...
    root_columns_url = f"https://api.zsxq.com/v2/columns?group_id={group_id}"
    resp = requests.get(root_columns_url, headers=headers)
    if resp.status_code == 200:
        print("Root Columns Metadata:")
        print(json.dumps(resp.json(), indent=2, ensure_ascii=False))
    else:
        print(f"Root Columns endpoint returned: {resp.status_code}")

if __name__ == "__main__":
    group_id = "15555442414282"
    inspect_group(group_id)
