from openai import OpenAI
import json
import logging
import re
import os
import time
import socket

logger = logging.getLogger(__name__)

class AIAnalyzer:
    def __init__(self, api_key=None, base_url="https://api.deepseek.com", provider="openai", gemini_key=None, gemini_model="gemini-2.0-flash", star_owner_name="pure日月"):
        self.provider = provider
        self.star_owner_name = star_owner_name
        self.system_prompt = f"""
You are a senior financial analyst. Analyze the following ZSXQ post content (including comments) to extract investment intelligence.
Analysis Rules:
1. **Star Owner Authority**: The Star Owner is **"{self.star_owner_name}"**. Their opinion (whether in post or comments) is the **highest authority**.
2. **Primary Focus**: If not the Star Owner, focus on the **Original Post Author's** Viewpoint.
3. **Author Replies**: Treat comments by the specific author (楼主) as high-priority supplements.
4. **Other Comments**: Use other users' comments only as:
   - Supplementary data/verification.
   - Significant counter-arguments (specify "Counter-argument from comments" in logic).
   - Do NOT let a random comment override the author's main suggestion unless the author admits error.

Extraction Requirements:
1. **Ticker**: Stocks, funds, sectors, or assets mentioned (e.g., AAPL, NASDAQ, Gold).
2. **Suggestion**: Buy, Sell, Hold, Add, Trim, etc. (Focus on Author's intent).
3. **Logic**: Core reasoning provided by the author. If comments add key info, append it.
4. **Language**: **ALL OUTPUT MUST BE IN SIMPLIFIED CHINESE (简体中文)**.

If content is irrelevant to investment, fill fields with "None"/"无".

Output JSON format:
{{
  "is_valuable": true/false (Is there valuable investment info?),
  "ticker": "标的名称 (中文)",
  "suggestion": "操作建议 (中文)",
  "logic": "逻辑简述 (中文)",
  "ai_summary": "一句话核心总结 (中文)"
}}
"""

        # Network connectivity check
        self._check_network_connectivity()
        
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
                logger.info(f"Gemini API Key configured: {gemini_key[:20]}...{gemini_key[-4:]}")
        else:
            # Default to OpenAI/DeepSeek
            self.client = OpenAI(api_key=api_key, base_url=base_url)
            logger.info(f"OpenAI/DeepSeek client initialized with base_url: {base_url}")

    def analyze_post(self, content):
        if self.provider == "gemini":
            return self._analyze_with_gemini(content)
        else:
            return self._analyze_with_openai(content)

    def _check_network_connectivity(self):
        """Check network connectivity to Google APIs"""
        try:
            socket.create_connection(("generativelanguage.googleapis.com", 443), timeout=5)
            logger.info("✓ Network connectivity check passed (Google APIs reachable)")
        except OSError as e:
            logger.error(f"✗ Network connectivity check failed: {e}")
            logger.error("Cannot reach generativelanguage.googleapis.com - check your internet connection")
    
    def _analyze_with_gemini(self, content):
        max_retries = 10
        import random
        base_wait_time = 30  # Start with 30 seconds
        
        # Log content preview for debugging
        content_preview = content[:200] + "..." if len(content) > 200 else content
        logger.debug(f"Analyzing content (preview): {content_preview}")
        logger.info(f"Content length: {len(content)} characters")

        for attempt in range(max_retries):
            try:
                logger.debug(f"Sending request to Gemini API (attempt {attempt + 1}/{max_retries})...")
                
                response = self.gemini_client.models.generate_content(
                    model=self.gemini_model,
                    contents=content,
                    config=self.types.GenerateContentConfig(
                        system_instruction=self.system_prompt,
                        response_mime_type="application/json"
                    )
                )
                
                # Log response details
                logger.debug(f"Received response from Gemini API")
                
                # Google GenAI SDK returns text in response.text
                text = response.text
                logger.debug(f"Response text (preview): {text[:200]}..." if len(text) > 200 else f"Response text: {text}")
                
                result = json.loads(text)
                logger.info(f"✓ Successfully parsed JSON response: is_valuable={result.get('is_valuable')}, ticker={result.get('ticker')}")
                return result
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")
                logger.error(f"Raw response text: {text}")
                return None
            except Exception as e:
                error_str = str(e)
                logger.error(f"Exception type: {type(e).__name__}")
                logger.error(f"Exception details: {error_str}")
                
                if "429" in error_str or "quota" in error_str.lower() or "resource_exhausted" in error_str.lower():
                    if attempt < max_retries - 1:
                        # Add jitter: +/- 20% of base_wait_time
                        jitter = random.uniform(0.8, 1.2)
                        wait_time = base_wait_time * jitter
                        logger.warning(f"⚠ Gemini 429 Quota Exceeded. Retrying in {wait_time:.1f}s... (Attempt {attempt + 1}/{max_retries})")
                        logger.warning(f"Rate limit hit - consider increasing GEMINI_REQUEST_DELAY")
                        time.sleep(wait_time)
                        base_wait_time *= 2  # Exponential backoff
                        continue
                    else:
                        logger.error(f"✗ Gemini analysis failed after {max_retries} attempts due to quota.")
                        logger.error(f"Suggestion: Increase GEMINI_REQUEST_DELAY or check your API quota")
                        return None
                else:
                    logger.error(f"✗ Gemini analysis failed: {e}")
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
