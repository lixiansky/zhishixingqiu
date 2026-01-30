# Zhishixingqiu Monitor (知识星球监控)

[![ZSXQ Monitor](https://github.com/lixiansky/zhishixingqiu/actions/workflows/zsxq_bot.yml/badge.svg)](https://github.com/lixiansky/zhishixingqiu/actions/workflows/zsxq_bot.yml)

一个基于 Python 的知识星球监控机器人，自动抓取指定星球的最新动态（主题、专栏、文件、问答），利用 AI 进行投资价值分析，并通过钉钉发送即时通知。

## ✨ 功能特性

- **多维度监控**：支持抓取星球内的普通主题、精华主题、专栏文章、文件分享及问答内容。
- **AI 智能分析**：集成 Google Gemini (推荐) 或 OpenAI/DeepSeek 接口，自动分析帖子内容，提取：
    - **投资标的** (Ticker)
    - **操作建议** (Suggestion)
    - **核心逻辑** (Logic)
    - **一句话总结** (Summary)
- **精准通知**：通过钉钉机器人发送 Markdown 格式的投资情报日报/即时通知。
- **数据持久化**：使用 SQLite 数据库 (`zsxq_investment.db`) 对已处理内容去重，避免重复推送。
- **自动化运行**：支持 GitHub Actions 定时任务（默认每小时运行一次），也可本地部署。

## 🚀 快速开始

### 1. 环境准备

确保已安装 Python 3.10+。

```bash
git clone https://github.com/lixiansky/zhishixingqiu.git
cd zhishixingqiu
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并填入以下信息：

```ini
# 必须配置
ZSXQ_COOKIE=your_zsxq_cookie_here       # 知识星球网页版 Cookie
DINGTALK_WEBHOOK=your_webhook_url       # 钉钉机器人 Webhook
DINGTALK_SECRET=your_secret_optional    # (可选) 钉钉机器人加签密钥

# AI 配置 (二选一)

# 方案 A: Google Gemini (推荐，免费额度高)
AI_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.0-flash
GEMINI_REQUEST_DELAY=15                 # 请求间隔(秒)，避免触发速率限制

# 方案 B: OpenAI / DeepSeek
# AI_PROVIDER=openai
# AI_API_KEY=sk-xxxxxx
# AI_BASE_URL=https://api.deepseek.com
```

### 3. 获取 Cookie

1. 浏览器访问 [知识星球网页版](https://wx.zsxq.com/) 并登录。
2. 按 `F12` 打开开发者工具，进入 `Network` 标签页。
3. 刷新页面，找到任意一个请求（如 `user_profile`），在 `Headers` 中复制 `Cookie` 的值。

### 4. 运行程序

**单次运行：**
```bash
python main.py
```

**启用内置定时任务（本地长期运行）：**
修改 `.env` 或代码中 `RUN_ONCE=false`。

## ⚙️ GitHub Actions 部署

本项目已配置好 GitHub Actions，Fork 本仓库后即可使用。

1. **Fork 本仓库**。
2. 进入仓库 **Settings** -> **Secrets and variables** -> **Actions**。
3. 添加以下 Repository secrets：
    - `ZSXQ_COOKIE`
    - `DINGTALK_WEBHOOK`
    - `DINGTALK_SECRET`
    - `GEMINI_API_KEY` (如果使用 Gemini)
4. Enable Workflow: 去 **Actions** 标签页启用 `ZSXQ Monitor` 工作流。

## 🛠️ 项目结构

- `main.py`: 程序入口，负责调度爬虫、分析器和通知器。
- `crawler.py`: 负责与知识星球 API 交互，获取各类数据。
- `analyzer.py`: 调用 AI 接口 (Gemini/OpenAI) 分析文本价值。
- `notifier.py`: 处理钉钉消息格式化与发送。
- `database.py`: SQLite 数据库操作，管理历史记录。
- `.github/workflows/zsxq_bot.yml`: GitHub Actions 定时任务配置。

## ⚠️ 注意事项

- **Cookie 有效期**：知识星球 Cookie 会定期失效，若程序报错 401/403，请更新 Secret 中的 Cookie。
- **API 频率限制**：Gemini 免费版有速率限制（RPM），建议保留 `GEMINI_REQUEST_DELAY` 设置。

## 📝 License

MIT License
