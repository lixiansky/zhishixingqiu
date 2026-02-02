import requests
import random
import time
import logging
import os

logger = logging.getLogger(__name__)

class ZsxqCrawler:
    def __init__(self, cookie, notifier=None):
        self.cookie = cookie
        self.notifier = notifier
        self.base_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Cookie': self.cookie,
            'Referer': 'https://wx.zsxq.com/',
            'Accept': 'application/json, text/plain, */*'
        }
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36'
        ]

    def _get_headers(self):
        headers = self.base_headers.copy()
        headers['User-Agent'] = random.choice(self.user_agents)
        return headers

    def _fetch_api(self, url):
        try:
            resp = requests.get(url, headers=self._get_headers(), timeout=15)
            if resp.status_code == 401:
                logger.error("Cookie expired or invalid (401).")
                if self.notifier:
                    self.notifier.notify_cookie_expired()
                return None
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    def get_user_groups(self):
        """获取用户加入的所有星球列表"""
        url = "https://api.zsxq.com/v2/groups"
        data = self._fetch_api(url)
        if not data or not data.get('succeeded'):
            return []
        
        resp = data.get('resp') or data.get('resp_data') or {}
        groups = resp.get('groups', [])
        
        result = []
        for group in groups:
            result.append({
                'group_id': group.get('group_id'),
                'name': group.get('name'),
                'type': group.get('type')
            })
        
        logger.info(f"Found {len(result)} groups")
        for g in result:
            logger.info(f"  - {g['name']} (ID: {g['group_id']})")
        
        return result
    
    @staticmethod
    def extract_group_id_from_url(url):
        """从知识星球 URL 中提取 group_id
        支持格式:
        - https://wx.zsxq.com/dweb2/index/group/[group_id]
        - https://wx.zsxq.com/group/[group_id]
        """
        import re
        match = re.search(r'/group/([0-9]+)', url)
        if match:
            return match.group(1)
        return None

    def resolve_group_id(self):
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
                group_id = self.extract_group_id_from_url(group_url)
                if group_id:
                    logger.info(f"从 URL 提取 group_id: {group_id}")
                    return group_id
                else:
                    error_msg = f"无法从 URL 中提取 group_id: {group_url}"
                    logger.error(error_msg)
                    if self.notifier:
                        self.notifier.notify_error("配置错误", error_msg, 
                            "请检查 ZSXQ_GROUP_URL 格式是否正确\n支持格式:\n- https://wx.zsxq.com/dweb2/index/group/[ID]\n- https://wx.zsxq.com/group/[ID]")
                    return None
            
            # 方式 3: 自动获取第一个星球
            logger.info("未配置 group_id，尝试自动获取...")
            groups = self.get_user_groups()
            
            if not groups:
                error_msg = "无法获取星球列表，可能是 Cookie 失效或网络问题"
                logger.error(error_msg)
                if self.notifier:
                    self.notifier.notify_error("API错误", error_msg,
                        "请检查:\n1. ZSXQ_COOKIE 是否有效\n2. 网络连接是否正常\n3. 是否至少加入了一个星球")
                return None
            
            group_id = groups[0]['group_id']
            logger.info(f"自动选择第一个星球: {groups[0]['name']} (ID: {group_id})")
            
            # 发送信息通知 (Only if notifier is present)
            if self.notifier:
                self.notifier.send_markdown(
                    "ℹ️ 知识星球监控启动",
                    f"### 自动选择星球\n\n**星球名称:** {groups[0]['name']}\n**Group ID:** {group_id}\n\n如需监控其他星球，请在 .env 文件中配置 ZSXQ_GROUP_ID 或 ZSXQ_GROUP_URL"
                )
            
            return group_id
            
        except Exception as e:
            error_msg = f"获取 group_id 时发生异常: {str(e)}"
            logger.error(error_msg, exc_info=True)
            if self.notifier:
                self.notifier.notify_error("系统错误", error_msg, 
                    f"异常类型: {type(e).__name__}\n请查看日志文件获取详细堆栈信息")
            return None

    def _extract_comments(self, topic):
        """提取帖子的回复信息"""
        # 尝试多个可能的字段名
        comments = topic.get('comments', []) or topic.get('show_comments', []) or topic.get('latest_comments', [])
        if not comments:
            return ""
        
        comment_texts = []
        for comment in comments:
            text = comment.get('text', '')
            author = comment.get('owner', {}).get('name', 'Unknown')
            if text:
                comment_texts.append(f"【{author}】: {text}")
        
        if comment_texts:
            return "\n\n--- 回复 ---\n" + "\n".join(comment_texts)
        return ""

    def get_group_topics(self, group_id, scope='all'):
        """
        scope: 'all' or 'digests'
        """
        url = f"https://api.zsxq.com/v2/groups/{group_id}/topics?scope={scope}&count=20"
        data = self._fetch_api(url)
        if not data or not data.get('succeeded'):
            return []
        
        # Determine section name based on scope
        section_name = "精华主题" if scope == 'digests' else "全部主题"
        
        resp = data.get('resp') or data.get('resp_data') or {}
        topics = resp.get('topics', [])
        results = []
        for t in topics:
            topic_id = t.get('topic_id')
            # Handle different content structures
            talk = t.get('talk', {})
            content = talk.get('text', '')
            author = talk.get('owner', {}).get('name', 'Unknown')
            create_time = t.get('create_time')
            url_link = f"https://wx.zsxq.com/dweb2/index/group/{group_id}/topic/{topic_id}"
            
            # Simple fallback for content
            if not content:
                article = t.get('article', {})
                content = f"{article.get('title', '')} {article.get('text', '')}"
            
            # Extract and append comments
            comments_text = self._extract_comments(t)
            full_content = content.strip() + comments_text
                
            results.append({
                'id': str(topic_id),
                'content': full_content,
                'author': author,
                'create_time': create_time,
                'url': url_link,
                'section_name': section_name
            })
        return results

    def get_column_articles(self, group_id, column_id, column_name="专栏"):
        url = f"https://api.zsxq.com/v2/groups/{group_id}/topics?scope=by_column&column_id={column_id}&count=20"
        data = self._fetch_api(url)
        if not data or not data.get('succeeded'):
            return []
        
        resp = data.get('resp') or data.get('resp_data') or {}
        topics = resp.get('topics', [])
        results = []
        for t in topics:
            topic_id = t.get('topic_id')
            # Handle different content structures
            talk = t.get('talk', {})
            content = talk.get('text', '')
            author = talk.get('owner', {}).get('name', 'Unknown')
            create_time = t.get('create_time')
            url_link = f"https://wx.zsxq.com/dweb2/index/group/{group_id}/topic/{topic_id}"
            
            # Simple fallback for content
            if not content:
                article = t.get('article', {})
                content = f"{article.get('title', '')} {article.get('text', '')}"
            
            # Fallback 2: Check for question/answer if mixed in
            if not content:
                q_and_a = t.get('question_answer', {})
                if q_and_a:
                    question = q_and_a.get('question', {}).get('text', '')
                    answer = q_and_a.get('answer', {}).get('text', '')
                    content = f"[问答]\n问：{question}\n答：{answer}"
            
            # Extract and append comments
            comments_text = self._extract_comments(t)
            full_content = content.strip() + comments_text

            results.append({
                'id': str(topic_id),
                'content': full_content,
                'author': author,
                'create_time': create_time,
                'url': url_link,
                'section_name': column_name
            })
        return results

    def get_group_columns(self, group_id):
        """
        Fetches the list of all columns associated with a group.
        """
        url = f"https://api.zsxq.com/v2/groups/{group_id}/columns"
        data = self._fetch_api(url)
        if not data or not data.get('succeeded'):
            return []
        
        resp = data.get('resp') or data.get('resp_data') or {}
        return resp.get('columns', [])

    def get_group_files(self, group_id):
        """
        Fetches the latest files shared in the group.
        """
        url = f"https://api.zsxq.com/v2/groups/{group_id}/files?count=20"
        data = self._fetch_api(url)
        if not data or not data.get('succeeded'):
            return []
        
        resp = data.get('resp') or data.get('resp_data') or {}
        files = resp.get('files', [])
        results = []
        for f in files:
            file_id = f.get('file_id')
            name = f.get('name')
            author = f.get('owner', {}).get('name', 'Unknown')
            create_time = f.get('create_time')
            # File URL in ZSXQ is often for downloading, we just record metadata
            url_link = f"https://wx.zsxq.com/group/{group_id}/files"
            
            results.append({
                'id': f"file_{file_id}",
                'content': f"[文件分享] {name}",
                'author': author,
                'create_time': create_time,
                'url': url_link,
                'section_name': "文件分享"
            })
        return results

    def get_group_questions(self, group_id):
        """
        Fetches Q&A content.
        """
        url = f"https://api.zsxq.com/v2/groups/{group_id}/topics?scope=q_and_a&count=20"
        data = self._fetch_api(url)
        if not data or not data.get('succeeded'):
            return []
        
        resp = data.get('resp') or data.get('resp_data') or {}
        topics = resp.get('topics', [])
        results = []
        for t in topics:
            topic_id = t.get('topic_id')
            q_and_a = t.get('question_answer', {})
            question = q_and_a.get('question', {}).get('text', '')
            answer = q_and_a.get('answer', {}).get('text', '')
            author = q_and_a.get('answer', {}).get('owner', {}).get('name', 'Unknown')
            create_time = t.get('create_time')
            url_link = f"https://wx.zsxq.com/dweb2/index/group/{group_id}/topic/{topic_id}"
            
            content = f"[问答]\n问：{question}\n答：{answer}"
            
            # Extract and append comments
            comments_text = self._extract_comments(t)
            full_content = content.strip() + comments_text
            
            results.append({
                'id': str(topic_id),
                'content': full_content,
                'author': author,
                'create_time': create_time,
                'url': url_link,
                'section_name': "问答"
            })
        return results

    def sleep_random(self):
        delay = random.uniform(30, 60)
        logger.info(f"Sleeping for {delay:.2f} seconds...")
        time.sleep(delay)
