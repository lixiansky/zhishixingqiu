import requests
import json
import logging
import time
import hmac
import hashlib
import base64
import urllib.parse
from datetime import datetime

logger = logging.getLogger(__name__)

class Notifier:
    def __init__(self, webhook_url, secret=None):
        self.webhook_url = webhook_url
        self.secret = secret
    
    def _format_time(self, time_str):
        """
        Convert ISO 8601 time string to readable Chinese format.
        Example: 2026-01-30T10:42:13.766+0800 -> 2026年01月30日 10:42
        """
        if not time_str:
            return ""
        
        try:
            # Parse ISO 8601 format
            # Handle both with and without timezone
            if '+' in time_str or time_str.endswith('Z'):
                # Remove timezone info for parsing
                time_str_clean = time_str.split('+')[0].split('Z')[0]
            else:
                time_str_clean = time_str
            
            # Parse datetime
            dt = datetime.fromisoformat(time_str_clean)
            
            # Format to Chinese readable format
            return dt.strftime("%Y年%m月%d日 %H:%M")
        except Exception as e:
            logger.warning(f"Failed to format time '{time_str}': {e}")
            return time_str

    def _get_signed_url(self):
        if not self.secret:
            return self.webhook_url
        
        timestamp = str(round(time.time() * 1000))
        secret_enc = self.secret.encode('utf-8')
        string_to_sign = '{}\n{}'.format(timestamp, self.secret)
        string_to_sign_enc = string_to_sign.encode('utf-8')
        hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        return f"{self.webhook_url}&timestamp={timestamp}&sign={sign}"

    def send_markdown(self, title, text):
        url = self._get_signed_url()
        headers = {'Content-Type': 'application/json'}
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": text
            }
        }
        try:
            resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=10)
            result = resp.json()
            if result.get('errcode') != 0:
                logger.error(f"DingTalk send failed: {result}")
            else:
                logger.info("DingTalk notification sent successfully.")
        except Exception as e:
            logger.error(f"Error sending to DingTalk: {e}")

    def notify_cookie_expired(self):
        title = "⚠️ 知识星球 Cookie 失效"
        content = "### ⚠️ 知识星球监控告警\n**状态：** Cookie 已失效 (401/403)\n**建议：** 请立即手动更新 `ZSXQ_COOKIE` 环境变量并重启程序。"
        self.send_markdown(title, content)

    def notify_investment_report(self, url, ticker, suggestion, logic, ai_summary, author=None, create_time=None, section_name=None):
        title = "📊 星球最新投资情报"
        
        # Format time if available
        time_str = ""
        if create_time:
            formatted_time = self._format_time(create_time)
            time_str = f"\n**发布时间：** {formatted_time}"
        
        author_str = ""
        if author:
            author_str = f"\n**作者：** {author}"
        
        section_str = ""
        if section_name:
            section_str = f"\n**板块：** {section_name}"
        
        content = f"""### 📊 星球最新投资情报

**原文链接：** [点击查看]({url}){section_str}{time_str}{author_str}

---

#### 📌 投资标的
{ticker}

#### 💡 操作建议
{suggestion}

#### 🔍 核心逻辑
{logic}

#### 🤖 AI 总结
{ai_summary}"""
        self.send_markdown(title, content)
