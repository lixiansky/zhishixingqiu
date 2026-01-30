from openai import OpenAI
import json
import logging
import re
import os
import time

logger = logging.getLogger(__name__)

class AIAnalyzer:
    def __init__(self, api_key=None, base_url="https://api.deepseek.com", provider="openai", gemini_key=None, gemini_model="gemini-2.0-flash"):
        self.provider = provider
        self.system_prompt = """
你是一位资深金融投资分析师。请分析以下知识星球帖子内容，提取投资情报。
你需要识别文中的：
1. 标的：提及的股票、基金、行业或资产（如：贵州茅台、纳斯达克100、黄金）。
2. 操作建议：文中的买入、卖出、持有、加仓、减仓等明确倾向。
3. 逻辑依据：作者提出该建议的核心理由。

如果内容与投资无关，请在字段中填入“无”。

请务必按以下 JSON 格式输出：
{
  "is_valuable": true/false (是否包含有价值的投资信息),
  "ticker": "标的名称",
  "suggestion": "建议内容",
  "logic": "逻辑简述",
  "ai_summary": "一句话核心总结"
}
"""
        if self.provider == "gemini":
            if not gemini_key:
                logger.error("Gemini provider selected but GEMINI_API_KEY is missing.")
            else:
                # Conditional import for Gemini
                from google import genai
                from google.genai import types
                self.gemini_client = genai.Client(api_key=gemini_key)
                self.gemini_model = gemini_model
                self.types = types
                logger.info(f"Gemini client initialized with model: {self.gemini_model}")
        else:
            # Default to OpenAI/DeepSeek
            self.client = OpenAI(api_key=api_key, base_url=base_url)

    def analyze_post(self, content):
        if self.provider == "gemini":
            return self._analyze_with_gemini(content)
        else:
            return self._analyze_with_openai(content)

    def _analyze_with_gemini(self, content):
        max_retries = 10
        import random
        base_wait_time = 30  # Start with 30 seconds

        for attempt in range(max_retries):
            try:
                response = self.gemini_client.models.generate_content(
                    model=self.gemini_model,
                    contents=content,
                    config=self.types.GenerateContentConfig(
                        system_instruction=self.system_prompt,
                        response_mime_type="application/json"
                    )
                )
                # Google GenAI SDK returns text in response.text
                text = response.text
                result = json.loads(text)
                return result
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "quota" in error_str.lower() or "resource_exhausted" in error_str.lower():
                    if attempt < max_retries - 1:
                        # Add jitter: +/- 20% of base_wait_time
                        jitter = random.uniform(0.8, 1.2)
                        wait_time = base_wait_time * jitter
                        logger.warning(f"Gemini 429 Quota Exceeded. Retrying in {wait_time:.1f}s... (Attempt {attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                        base_wait_time *= 2  # Exponential backoff
                        continue
                    else:
                        logger.error(f"Gemini analysis failed after {max_retries} attempts due to quota. Please check your plan.")
                        return None
                else:
                    logger.error(f"Gemini analysis failed: {e}")
                    return None

    def _analyze_with_openai(self, content):
        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat", # 或者 gpt-4, gpt-3.5-turbo 等
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": content},
                ],
                response_format={ 'type': 'json_object' }
            )
            result = json.loads(response.choices[0].message.content)
            return result
        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            return None

    def clean_json(self, raw_str):
        # Fallback helper
        match = re.search(r'\{.*\}', raw_str, re.DOTALL)
        if match:
            return json.loads(match.group())
        return None
