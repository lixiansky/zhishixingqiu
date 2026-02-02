# Zhishixingqiu Monitor (知识星球监控)

[![ZSXQ Monitor](https://github.com/lixiansky/zhishixingqiu/actions/workflows/zsxq-monitor.yml/badge.svg)](https://github.com/lixiansky/zhishixingqiu/actions/workflows/zsxq-monitor.yml)

一个基于 Python 的知识星球监控机器人，自动抓取指定星球的最新动态（主题、专栏、文件、问答），利用 AI 进行投资价值分析，并通过钉钉发送即时通知。

## ✨ 功能特性

- **多维度监控**:支持抓取星球内的普通主题、精华主题、专栏文章、文件分享及问答内容。
- **深度内容提取**:自动提取帖子的评论回复,结合原文和评论进行全面分析。
- **灵活配置**:支持三种方式配置星球 ID,可直接配置、URL 提取或自动识别,无需修改代码。
- **AI 智能分析**:集成 Google Gemini (推荐) 或 OpenAI/DeepSeek 接口,自动分析帖子内容,提取:
    - **投资标的** (Ticker)
    - **操作建议** (Suggestion)
    - **核心逻辑** (Logic)
    - **一句话总结** (Summary)
    - **星球主权威识别**:可配置星球主名称,AI 优先采纳星球主观点
- **精准通知**:通过钉钉机器人发送 Markdown 格式的投资情报日报/即时通知。
- **智能告警**:自动检测 Cookie 失效(401/403)及配置错误,及时发送钉钉告警通知。
- **数据持久化**:使用 SQLite 数据库 (`zsxq_investment.db`) 对已处理内容去重,避免重复推送。
- **自动化运行**:支持 GitHub Actions 定时任务(默认白天每 20 分钟, 晚间每 1 小时),也可本地部署。

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

# 知识星球配置 (三选一)
# 方式 1: 直接配置 group_id (推荐,性能最好)
ZSXQ_GROUP_ID=your_group_id_here

# 方式 2: 配置星球主页 URL (用户友好,自动提取 ID)
# ZSXQ_GROUP_URL=https://wx.zsxq.com/dweb2/index/group/your_group_id

# 方式 3: 不配置，程序会自动使用您加入的第一个星球 (零配置)
# 注意: 首次使用方式3时，会通过钉钉通知您选择的星球

# AI 配置 (二选一)

# 方案 A: Google Gemini (推荐,免费额度高)
AI_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.0-flash
GEMINI_REQUEST_DELAY=15                 # 请求间隔(秒),避免触发速率限制

# 方案 B: OpenAI / DeepSeek
# AI_PROVIDER=openai
# AI_API_KEY=sk-xxxxxx
# AI_BASE_URL=https://api.deepseek.com

# 星球主名称配置 (必填,AI 分析时优先采纳此用户的观点)
STAR_OWNER_NAME=your_star_owner_name_here  # 请修改为您的星球主名称
```

### 3. 获取配置信息

#### 获取 Cookie
1. 浏览器访问 [知识星球网页版](https://wx.zsxq.com/) 并登录。
2. 按 `F12` 打开开发者工具，进入 `Network` 标签页。
3. 刷新页面，找到任意一个请求（如 `user_profile`），在 `Headers` 中复制 `Cookie` 的值。

#### 获取 Group ID (可选)
**方式 1: 从浏览器地址栏获取**
1. 访问您要监控的星球主页
2. 地址栏 URL 格式为: `https://wx.zsxq.com/dweb2/index/group/[这里就是group_id]`
3. 复制数字部分即可

**方式 2: 直接使用 URL**
- 直接将星球主页 URL 配置到 `ZSXQ_GROUP_URL`,程序会自动提取 ID

**方式 3: 自动获取**
- 不配置任何 group_id,程序会自动使用您加入的第一个星球

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
    - `ZSXQ_COOKIE` (必填)
    - `DINGTALK_WEBHOOK` (必填)
    - `DINGTALK_SECRET` (可选)
    - `ZSXQ_GROUP_ID` 或 `ZSXQ_GROUP_URL` (推荐配置,不配置则自动使用第一个星球)
    - `STAR_OWNER_NAME` (必填,星球主名称)
    - `GEMINI_API_KEY` (如果使用 Gemini)
    - `AI_API_KEY` (如果使用 OpenAI/DeepSeek)
4. Enable Workflow: 去 **Actions** 标签页启用 `ZSXQ Monitor` 工作流。

## 🛠️ 项目结构

- `main.py`: 程序入口,负责调度爬虫、分析器和通知器。
- `crawler.py`: 负责与知识星球 API 交互,获取各类数据(含评论提取和 Cookie 过期检测)。
- `analyzer.py`: 调用 AI 接口 (Gemini/OpenAI) 分析文本价值,支持星球主权威识别。
- `notifier.py`: 处理钉钉消息格式化与发送,包括 Cookie 过期告警。
- `database.py`: SQLite/PostgreSQL 数据库操作,管理历史记录。
- `.github/workflows/zsxq-monitor.yml`: GitHub Actions 主监控工作流(白天每 20 分钟, 晚间每 1 小时)。
- `.github/workflows/analyze-only.yml`: 仅分析工作流(每 6 小时)。
- `.github/workflows/manual-backfill.yml`: 手动回填评论工作流。

## ⚠️ 注意事项

- **星球配置**:
  - 推荐使用方式 1 (直接配置 `ZSXQ_GROUP_ID`) 或方式 2 (配置 `ZSXQ_GROUP_URL`)
  - 使用方式 3 (自动获取) 时,首次运行会通过钉钉通知您选择的星球
  - 如需切换监控的星球,只需修改环境变量即可,无需改动代码
- **Cookie 自动监控**:程序会自动检测 Cookie 失效(401/403),并通过钉钉发送告警通知,提醒您及时更新 `ZSXQ_COOKIE`。
- **错误通知**:所有配置错误、API 错误、系统异常都会通过钉钉推送,便于及时发现和处理问题。
- **API 频率限制**:Gemini 免费版有速率限制(RPM),建议保留 `GEMINI_REQUEST_DELAY` 设置。
- **星球主配置**:必须在环境变量中设置 `STAR_OWNER_NAME` 为您的星球主名称,确保 AI 正确识别权威观点。
- **评论深度分析**:程序会自动提取帖子评论,AI 会综合原文和评论进行分析,星球主的评论具有最高优先级。

## 📝 License

MIT License
