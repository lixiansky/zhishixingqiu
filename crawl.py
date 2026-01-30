import os
import sys
import logging
from dotenv import load_dotenv
from database import Database
from crawler import ZsxqCrawler
from notifier import Notifier

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("crawl.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("Crawler")

def fetch_all_data(crawler, group_id):
    """抓取所有数据源"""
    fetched_data = []
    
    # A. Fetch Group Topics
    logger.info("Fetching Group topics (all & digests)...")
    fetched_data.extend(crawler.get_group_topics(group_id, scope='digests'))
    fetched_data.extend(crawler.get_group_topics(group_id, scope='all'))
    
    # B. Fetch Dynamic Columns
    logger.info("Discovering and fetching Column articles...")
    columns = crawler.get_group_columns(group_id)
    for col in columns:
        col_id = col.get('column_id')
        col_name = col.get('name')
        logger.info(f"Fetching articles from column: {col_name} ({col_id})")
        fetched_data.extend(crawler.get_column_articles(group_id, col_id, col_name))
    
    # C. Fetch Files
    logger.info("Fetching Group files...")
    fetched_data.extend(crawler.get_group_files(group_id))
    
    # D. Fetch Questions
    logger.info("Fetching Group questions...")
    fetched_data.extend(crawler.get_group_questions(group_id))
    
    return fetched_data

def save_new_posts(db, fetched_data):
    """保存新帖子到数据库"""
    new_posts_count = 0
    for post in fetched_data:
        if not db.post_exists(post['id']):
            db.save_post(
                post['id'], 
                post['content'], 
                post['author'], 
                post['create_time'], 
                post['url'],
                post.get('section_name')
            )
            new_posts_count += 1
    return new_posts_count

def main():
    # 初始化
    cookie = os.getenv("ZSXQ_COOKIE")
    ding_url = os.getenv("DINGTALK_WEBHOOK")
    ding_secret = os.getenv("DINGTALK_SECRET")
    group_id = "15555442414282"
    auto_analyze = os.getenv("AUTO_ANALYZE_AFTER_CRAWL", "true").lower() == "true"
    
    if not cookie:
        logger.error("ZSXQ_COOKIE is not set!")
        return 1
    
    db = Database()
    notifier = Notifier(ding_url, ding_secret)
    crawler = ZsxqCrawler(cookie, notifier)
    
    logger.info("Starting crawl cycle...")
    
    # 抓取数据
    fetched_data = fetch_all_data(crawler, group_id)
    
    # 保存新帖子
    new_count = save_new_posts(db, fetched_data)
    
    logger.info(f"Crawl complete. Found {len(fetched_data)} total items, {new_count} new posts.")
    
    # 如果有新帖子且启用自动分析,则调用分析脚本
    if new_count > 0 and auto_analyze:
        logger.info(f"Found {new_count} new posts. Triggering analysis...")
        import subprocess
        result = subprocess.run([sys.executable, "analyze.py"], cwd=os.path.dirname(__file__) or ".")
        return result.returncode
    else:
        if new_count == 0:
            logger.info("No new posts to analyze.")
        else:
            logger.info("Auto-analyze disabled. Skipping analysis.")
        return 0

if __name__ == "__main__":
    sys.exit(main())
