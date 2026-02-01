import os
import sys
import time
import logging
from dotenv import load_dotenv
from database import Database
from analyzer import AIAnalyzer
from notifier import Notifier

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("analyze.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("Analyzer")

class RateLimiter:
    """速率限制器"""
    def __init__(self, requests_per_minute=15):
        self.rpm = requests_per_minute
        self.interval = 60.0 / requests_per_minute
        self.last_request = 0
    
    def wait(self):
        """等待直到可以发送下一个请求"""
        elapsed = time.time() - self.last_request
        if elapsed < self.interval:
            wait_time = self.interval - elapsed
            logger.info(f"Rate limiting: waiting {wait_time:.2f}s...")
            time.sleep(wait_time)
        self.last_request = time.time()

def is_valid_post(pid, content, author, section_name):
    """验证帖子数据是否有效"""
    # 过滤无效 ID
    if not pid or pid == "file_None" or "None" in str(pid):
        logger.warning(f"Invalid post ID: {pid}")
        return False
    
    # 过滤空内容或内容过短
    if not content or len(content.strip()) < 50:
        logger.warning(f"Content too short for post {pid}: {len(content) if content else 0} chars")
        return False
    
    # 过滤文件分享页面（通常内容很短且无实际投资信息）
    if section_name == "文件分享" and len(content) < 100:
        logger.warning(f"Skipping file sharing post {pid} with short content")
        return False
    
    # 过滤未知作者且内容过短的帖子
    if author == "Unknown" and len(content) < 200:
        logger.warning(f"Skipping unknown author post {pid} with short content")
        return False
    
    return True

def main():
    # 配置
    ai_api_key = os.getenv("AI_API_KEY")
    ai_base_url = os.getenv("AI_BASE_URL", "https://api.deepseek.com")
    ai_provider = os.getenv("AI_PROVIDER", "openai")
    gemini_key = os.getenv("GEMINI_API_KEY")
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    star_owner_name = os.getenv("STAR_OWNER_NAME")
    
    ding_url = os.getenv("DINGTALK_WEBHOOK")
    ding_secret = os.getenv("DINGTALK_SECRET")
    
    # 速率控制配置
    max_posts_per_run = int(os.getenv("MAX_POSTS_PER_RUN", "10"))
    requests_per_minute = int(os.getenv("AI_REQUESTS_PER_MINUTE", "10"))
    
    # 初始化
    db = Database()
    analyzer = AIAnalyzer(
        ai_api_key, 
        ai_base_url, 
        provider=ai_provider, 
        gemini_key=gemini_key, 
        gemini_model=gemini_model,
        star_owner_name=star_owner_name
    )
    notifier = Notifier(ding_url, ding_secret)
    rate_limiter = RateLimiter(requests_per_minute=requests_per_minute)
    
    # 获取未分析帖子数量
    total_unanalyzed = db.get_unanalyzed_count()
    logger.info(f"DEBUG: Total unanalyzed posts returned by DB: {total_unanalyzed}")
    
    if total_unanalyzed == 0:
        logger.info("No posts to analyze. Exiting.")
        return 0
    
    # 获取本次要分析的帖子(限制数量)
    logger.info(f"DEBUG: Attempting to fetch max {max_posts_per_run} posts...")
    unanalyzed = db.get_unanalyzed_posts(limit=max_posts_per_run)
    logger.info(f"DEBUG: Fetched {len(unanalyzed)} posts for analysis.")
    logger.info(f"Analyzing {len(unanalyzed)} posts (max: {max_posts_per_run})...")
    
    # 逐个分析
    success_count = 0
    valuable_count = 0
    
    for idx, (pid, content, url, author, create_time, section_name) in enumerate(unanalyzed, 1):
        logger.info(f"[{idx}/{len(unanalyzed)}] Processing post {pid}...")
        
        # 数据验证
        if not is_valid_post(pid, content, author, section_name):
            logger.info(f"  ⊘ Skipped invalid post {pid}")
            # 标记为已分析（避免重复处理）
            db.update_analysis(pid, "无效数据", "跳过", "数据验证失败", "此帖子数据无效，已跳过分析")
            continue
        
        logger.info(f"  ✓ Post validation passed")
        logger.info(f"  Post ID: {pid}")
        logger.info(f"  Author: {author}")
        logger.info(f"  Section: {section_name}")
        logger.info(f"  URL: {url}")
        logger.info(f"  Content length: {len(content)} chars")
        
        # Log content preview
        content_preview = content[:300] + "..." if len(content) > 300 else content
        logger.debug(f"  Content preview: {content_preview}")
        
        try:
            # 速率限制
            rate_limiter.wait()
            
            # AI分析
            logger.info(f"  Sending to AI analyzer...")
            analysis = analyzer.analyze_post(content)
            
            if analysis:
                logger.info(f"  ✓ Analysis successful!")
                logger.info(f"    - is_valuable: {analysis.get('is_valuable')}")
                logger.info(f"    - ticker: {analysis.get('ticker', '无')}")
                logger.info(f"    - suggestion: {analysis.get('suggestion', '无')}")
                logger.info(f"    - logic: {analysis.get('logic', '无')[:100]}..." if len(analysis.get('logic', '')) > 100 else f"    - logic: {analysis.get('logic', '无')}")
                logger.info(f"    - ai_summary: {analysis.get('ai_summary', '无')}")
                
                # 更新数据库
                db.update_analysis(
                    pid,
                    analysis.get('ticker', '无'),
                    analysis.get('suggestion', '无'),
                    analysis.get('logic', '无'),
                    analysis.get('ai_summary', '无')
                )
                success_count += 1
                logger.info(f"  ✓ Database updated for post {pid}")
                
                # 发送通知(如果有价值)
                if analysis.get('is_valuable'):
                    valuable_count += 1
                    logger.info(f"  📢 Valuable info found! Sending DingTalk notification...")
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
                    logger.info(f"  ✓ Notification sent")
                else:
                    logger.info(f"  ℹ Post {pid} analyzed but not valuable (no notification sent)")
            else:
                logger.warning(f"  ✗ Failed to analyze post {pid} - analyzer returned None")
                
        except Exception as e:
            logger.error(f"Error analyzing post {pid}: {e}")
            continue
    
    # 统计信息
    remaining = total_unanalyzed - success_count
    logger.info(f"Analysis complete. Processed: {success_count}/{len(unanalyzed)}, Valuable: {valuable_count}, Remaining: {remaining}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
