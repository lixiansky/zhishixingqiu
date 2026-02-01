import os
import logging
from dotenv import load_dotenv
from typing import List, Dict

from crawler import ZsxqCrawler
from database import Database
from crawl import fetch_all_data

# Load environment variables
load_dotenv()

# Logger setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def backfill_data(group_id: str):
    """
    Backfill data by re-crawling and resolving comments.
    Existing posts will be updated with new content (including comments) 
    and their analyzed status will be reset.
    """
    cookie = os.getenv('ZSXQ_COOKIE')
    if not cookie:
        logger.error("ZSXQ_COOKIE not found in .env")
        return

    logger.info("Starting backfill process...")
    
    # Initialize components
    db = Database()
    crawler = ZsxqCrawler(cookie)
    
    # Fetch all data (now includes comments via updated Crawler)
    try:
        fetched_data = fetch_all_data(crawler, group_id)
        if not fetched_data:
            logger.warning("No data fetched.")
            return
    except Exception as e:
        logger.error(f"Error fetching data: {e}")
        return

    logger.info(f"Fetched {len(fetched_data)} items. Processing updates...")
    
    updated_count = 0
    new_count = 0 
    
    for post in fetched_data:
        post_id = post['id']
        content = post['content']
        
        if db.post_exists(post_id):
            # Update existing post
            logger.info(f"Updating post {post_id} with new content (comments included)...")
            success = db.update_post_content(post_id, content)
            if success:
                updated_count += 1
        else:
            # Save new post
            logger.info(f"Saving new post {post_id}...")
            success = db.save_post(
                post_id, 
                content, 
                post['author'], 
                post['create_time'], 
                post['url'],
                post.get('section_name')
            )
            if success:
                new_count += 1
    
    logger.info("Backfill complete.")
    logger.info(f"Total processed: {len(fetched_data)}")
    logger.info(f"Updated posts: {updated_count}")
    logger.info(f"New posts added: {new_count}")

if __name__ == "__main__":
    # 初始化
    cookie = os.getenv('ZSXQ_COOKIE')
    ding_url = os.getenv("DINGTALK_WEBHOOK")
    ding_secret = os.getenv("DINGTALK_SECRET")
    
    if not cookie:
        logger.error("ZSXQ_COOKIE not found in .env")
        sys.exit(1)
    
    notifier = Notifier(ding_url, ding_secret)
    crawler = ZsxqCrawler(cookie, notifier)
    
    # 动态获取 group_id (使用与 crawl.py 相同的逻辑)
    try:
        group_id = os.getenv("ZSXQ_GROUP_ID")
        if not group_id:
            group_url = os.getenv("ZSXQ_GROUP_URL")
            if group_url:
                group_id = ZsxqCrawler.extract_group_id_from_url(group_url)
        
        if not group_id:
            logger.info("未配置 group_id，尝试自动获取...")
            groups = crawler.get_user_groups()
            if groups:
                group_id = groups[0]['group_id']
                logger.info(f"自动选择第一个星球: {groups[0]['name']} (ID: {group_id})")
        
        if not group_id:
            logger.error("无法获取 group_id，请配置 ZSXQ_GROUP_ID 或 ZSXQ_GROUP_URL")
            sys.exit(1)
            
        backfill_data(group_id)
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)

