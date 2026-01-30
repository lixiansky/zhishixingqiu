
import os
import logging
from dotenv import load_dotenv
from crawler import ZsxqCrawler

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DebugZsxq")

def debug_columns():
    cookie = os.getenv("ZSXQ_COOKIE")
    if not cookie:
        print("Error: ZSXQ_COOKIE not found")
        return

    crawler = ZsxqCrawler(cookie)
    group_id = "15555442414282" 
    
    print(f"Fetching columns for group {group_id}...")
    columns = crawler.get_group_columns(group_id)
    
    target_col_id = "881484845122" 
    
    # Test 1: v2/columns/{id}/topics
    print(f"Testing v2/columns/{target_col_id}/topics ...")
    url_1 = f"https://api.zsxq.com/v2/columns/{target_col_id}/topics?count=5"
    res_1 = crawler._fetch_api(url_1)
    if res_1: print("Success 1")
    else: print("Failed 1")
    
    # Test 2: v2/groups/{gid}/topics?scope=by_column&column_id={id}
    print(f"Testing v2/groups/{group_id}/topics?scope=by_column&column_id={target_col_id} ...")
    url_2 = f"https://api.zsxq.com/v2/groups/{group_id}/topics?scope=by_column&column_id={target_col_id}&count=5"
    res_2 = crawler._fetch_api(url_2)
    if res_2: print("Success 2") 
    else: print("Failed 2")

    # Test 3: v2/groups/{gid}/topics?column_id={id}
    print(f"Testing v2/groups/{group_id}/topics?column_id={target_col_id} ...")
    url_3 = f"https://api.zsxq.com/v2/groups/{group_id}/topics?column_id={target_col_id}&count=5"
    res_3 = crawler._fetch_api(url_3)
    if res_3: print("Success 3")
    else: print("Failed 3")
        
if __name__ == "__main__":
    debug_columns()
