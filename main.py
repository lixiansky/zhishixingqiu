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
    
    group_id = "15555442414282"  # Based on the user's provided URLs

    if not cookie:
        logger.error("ZSXQ_COOKIE is not set! Please check your .env file.")
        return

    db = Database()
    notifier = Notifier(ding_url, ding_secret)
    crawler = ZsxqCrawler(cookie, notifier)
    analyzer = AIAnalyzer(ai_api_key, ai_base_url, provider=ai_provider, gemini_key=gemini_key, gemini_model=gemini_model)

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
