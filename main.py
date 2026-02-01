import os
import time
import logging
import schedule
from dotenv import load_dotenv

from database import Database
from crawler import ZsxqCrawler
from analyzer import AIAnalyzer
from notifier import Notifier

# Load environment variables
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("zsxq.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ZsxqMain")

def get_group_id(crawler, notifier):
    """动态获取 group_id
    优先级:
    1. 环境变量 ZSXQ_GROUP_ID
    2. 环境变量 ZSXQ_GROUP_URL (提取 ID)
    3. 自动获取第一个星球
    """
    try:
        # 方式 1: 直接配置 ID
        group_id = os.getenv("ZSXQ_GROUP_ID")
        if group_id:
            logger.info(f"使用配置的 group_id: {group_id}")
            return group_id
        
        # 方式 2: 从 URL 提取
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
        
        # 方式 3: 自动获取第一个星球
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
        
        # 发送信息通知
        notifier.send_markdown(
            "ℹ️ 知识星球监控启动",
            f"### 自动选择星球\n\n**星球名称:** {groups[0]['name']}\n**Group ID:** {group_id}\n\n如需监控其他星球，请在 .env 文件中配置 ZSXQ_GROUP_ID 或 ZSXQ_GROUP_URL"
        )
        
        return group_id
        
    except Exception as e:
        error_msg = f"获取 group_id 时发生异常: {str(e)}"
        logger.error(error_msg, exc_info=True)  # 完整堆栈信息记录在日志中
        # 钉钉通知仅包含异常类型和简要描述
        notifier.notify_error("系统错误", error_msg, 
            f"异常类型: {type(e).__name__}\n请查看日志文件获取详细堆栈信息")
        return None


def run_task():
    # 1. Initialization
    cookie = os.getenv("ZSXQ_COOKIE")
    ding_url = os.getenv("DINGTALK_WEBHOOK")
    ding_secret = os.getenv("DINGTALK_SECRET")
    ai_api_key = os.getenv("AI_API_KEY")
    ai_base_url = os.getenv("AI_BASE_URL", "https://api.deepseek.com")
    ai_provider = os.getenv("AI_PROVIDER", "openai")
    gemini_key = os.getenv("GEMINI_API_KEY")
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    # Default to 15 seconds to be safe within 15 RPM limit (1 req / 4 sec + buffer)
    request_delay = int(os.getenv("GEMINI_REQUEST_DELAY", "5"))
    star_owner_name = os.getenv("STAR_OWNER_NAME")

    if not cookie:
        logger.error("ZSXQ_COOKIE is not set! Please check your .env file.")
        return

    db = Database()
    notifier = Notifier(ding_url, ding_secret)
    crawler = ZsxqCrawler(cookie, notifier)
    analyzer = AIAnalyzer(ai_api_key, ai_base_url, provider=ai_provider, gemini_key=gemini_key, gemini_model=gemini_model, star_owner_name=star_owner_name)

    # 动态获取 group_id
    group_id = get_group_id(crawler, notifier)
    
    if not group_id:
        logger.error("无法获取 group_id，程序退出")
        return

    logger.info("Starting crawl cycle...")

    # 2. Fetch data from different parts
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

    # 3. Store new posts
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
    
    logger.info(f"Cycle complete. Found {len(fetched_data)} raw items, {new_posts_count} new.")

    # 4. Analyze unanalyzed posts
    unanalyzed = db.get_unanalyzed_posts()
    for pid, content, url, author, create_time, section_name in unanalyzed:
        logger.info(f"Analyzing post {pid}...")
        analysis = analyzer.analyze_post(content)
        
        if analysis:
            # Update DB
            db.update_analysis(
                pid,
                analysis.get('ticker', '无'),
                analysis.get('suggestion', '无'),
                analysis.get('logic', '无'),
                analysis.get('ai_summary', '无')
            )
            
            # 5. Notify if valuable
            if analysis.get('is_valuable'):
                logger.info(f"Valuable info found in post {pid}, sending notification.")
                notifier.notify_investment_report(
                    url,
                    analysis.get('ticker'),
                    analysis.get('suggestion'),
                    analysis.get('logic'),
                    analysis.get('ai_summary'),
                    author=author,
                    create_time=create_time,
                    section_name=section_name
                )
        else:
            logger.warning(f"Failed to analyze post {pid}")
        
        # Add delay to respect rate limits (especially for Gemini Free Tier)
        logger.info(f"Analysis complete. Sleeping for {request_delay}s to respect rate limits...")
        time.sleep(request_delay)

def main():
    # Run once at startup
    run_task()
    
    if os.getenv("RUN_ONCE", "false").lower() == "true":
        logger.info("RUN_ONCE is set. Exiting after single run.")
        return

    # Schedule every 2 hours (adjust as needed)
    schedule.every(2).hours.do(run_task)
    
    logger.info("Scheduler started. Running every 2 hours.")
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()
