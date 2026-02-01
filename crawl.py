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

def get_group_id(crawler, notifier):
    """动态获取 group_id (与 main.py 中的实现相同)"""
    try:
        group_id = os.getenv("ZSXQ_GROUP_ID")
        if group_id:
            logger.info(f"使用配置的 group_id: {group_id}")
            return group_id
        
        group_url = os.getenv("ZSXQ_GROUP_URL")
        if group_url:
            group_id = ZsxqCrawler.extract_group_id_from_url(group_url)
            if group_id:
                logger.info(f"从 URL 提取 group_id: {group_id}")
                return group_id
            else:
                error_msg = f"无法从 URL 中提取 group_id: {group_url}"
                logger.error(error_msg)
                notifier.notify_error("配置错误", error_msg, 
                    "请检查 ZSXQ_GROUP_URL 格式是否正确\n支持格式:\n- https://wx.zsxq.com/dweb2/index/group/[ID]\n- https://wx.zsxq.com/group/[ID]")
                return None
        
        logger.info("未配置 group_id，尝试自动获取...")
        groups = crawler.get_user_groups()
        
        if not groups:
            error_msg = "无法获取星球列表，可能是 Cookie 失效或网络问题"
            logger.error(error_msg)
            notifier.notify_error("API错误", error_msg,
                "请检查:\n1. ZSXQ_COOKIE 是否有效\n2. 网络连接是否正常\n3. 是否至少加入了一个星球")
            return None
        
        group_id = groups[0]['group_id']
        logger.info(f"自动选择第一个星球: {groups[0]['name']} (ID: {group_id})")
        return group_id
        
    except Exception as e:
        error_msg = f"获取 group_id 时发生异常: {str(e)}"
        logger.error(error_msg, exc_info=True)
        notifier.notify_error("系统错误", error_msg, 
            f"异常类型: {type(e).__name__}\n请查看日志文件获取详细堆栈信息")
        return None

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
    auto_analyze = os.getenv("AUTO_ANALYZE_AFTER_CRAWL", "true").lower() == "true"
    
    if not cookie:
        logger.error("ZSXQ_COOKIE is not set!")
        return 1
    
    db = Database()
    notifier = Notifier(ding_url, ding_secret)
    crawler = ZsxqCrawler(cookie, notifier)
    
    # 动态获取 group_id
    group_id = get_group_id(crawler, notifier)
    if not group_id:
        logger.error("无法获取 group_id，程序退出")
        return 1
    
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
