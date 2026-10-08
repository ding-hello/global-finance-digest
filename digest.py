#!/usr/bin/env python3
"""
全球财经与综合热点每日早报推送脚本
- 定时抓取全球财经、宏观市场与综合头条 RSS
- 支持大模型 (Gemini / OpenAI / DeepSeek) 智能提炼要闻
- 通过 Bark 推送到 iPhone 锁屏弹窗
"""

import os
import sys
import json
import logging
from datetime import datetime
import feedparser
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# 优质公开新闻 RSS 源（全球财经 + 综合热点）
FEEDS = {
    "财经/宏观": [
        "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=zh-CN&gl=CN&ceid=CN:zh-Hans",
        "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-US&gl=US&ceid=US:en",
    ],
    "全球/综合头条": [
        "https://news.google.com/rss?hl=zh-CN&gl=CN&ceid=CN:zh-Hans",
        "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en",
    ]
}


def fetch_news(max_per_category=6):
    """抓取并清洗各分类新闻"""
    collected = {}
    for cat, urls in FEEDS.items():
        items = []
        for url in urls:
            try:
                logging.info(f"正在拉取源: {url}")
                feed = feedparser.parse(url)
                for entry in feed.entries[:max_per_category]:
                    title = entry.get("title", "").strip()
                    link = entry.get("link", "")
                    if title and not any(t["title"] == title for t in items):
                        items.append({"title": title, "link": link})
            except Exception as e:
                logging.warning(f"拉取失败 {url}: {e}")
        collected[cat] = items[:max_per_category]
    return collected


def generate_summary_with_ai(news_data):
    """若配置了 API Key，则调用大模型提炼；否则返回精美纯文本排版"""
    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    openai_base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model_name = os.getenv("MODEL_NAME", "gpt-4o-mini")

    raw_text = ""
    for cat, items in news_data.items():
        raw_text += f"\n【{cat}】\n"
        for idx, item in enumerate(items, 1):
            raw_text += f"{idx}. {item['title']}\n"

    prompt = f"""你是一名资深宏观经济分析师与科技简报编辑。请根据以下今日抓取的全球财经与综合热点，提炼出一份精炼的“iPhone 弹窗/晨读要闻速递”。

要求：
1. 分类为：【全球宏观与市场】、【产业与重磅事件】、【热点聚焦】。
2. 每个分类提炼 2~3 条最具价值的要闻，用一句话提炼核心影响，语言干练专业。
3. 最后附一句今日市场/趋势观察。
4. 全文控制在 400 字以内，排版清爽，适合手机屏幕速读。

原始新闻列表：
{raw_text}
"""

    # 1. 尝试调用 Gemini API
    if gemini_key:
        try:
            logging.info("使用 Gemini API 总结要闻...")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            res = requests.post(url, json=payload, timeout=30)
            if res.status_code == 200:
                data = res.json()
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()
            else:
                logging.warning(f"Gemini API 响应异常: {res.text}")
        except Exception as e:
            logging.warning(f"Gemini API 调用出错: {e}")

    # 2. 尝试调用 OpenAI 兼容 API (如 DeepSeek / OpenAI)
    if openai_key:
        try:
            logging.info("使用 OpenAI 兼容 API 总结要闻...")
            headers = {"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"}
            payload = {
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.5
            }
            res = requests.post(f"{openai_base}/chat/completions", headers=headers, json=payload, timeout=30)
            if res.status_code == 200:
                data = res.json()
                return data["choices"][0]["message"]["content"].strip()
            else:
                logging.warning(f"OpenAI API 响应异常: {res.text}")
        except Exception as e:
            logging.warning(f"OpenAI API 调用出错: {e}")

    # 3. 兜底备选：无 Key 时的结构化排版
    logging.info("未配置大模型 API Key 或调用失败，使用内置格式化排版")
    lines = []
    for cat, items in news_data.items():
        lines.append(f"【{cat}】")
        for idx, item in enumerate(items[:4], 1):
            title = item['title'].split(" - ")[0]  # 去除来源后缀
            lines.append(f"• {title}")
        lines.append("")
    return "\n".join(lines).strip()


def send_to_bark(title, body):
    """通过 Bark 推送到 iPhone"""
    bark_key = os.getenv("BARK_KEY")
    bark_server = os.getenv("BARK_SERVER", "https://api.day.app")

    if not bark_key:
        logging.error("未找到 BARK_KEY 环境变量！请在 GitHub Secrets 中配置 BARK_KEY。")
        sys.exit(1)

    url = f"{bark_server.rstrip('/')}/{bark_key}/"
    payload = {
        "title": title,
        "body": body,
        "group": "全球财经速递",
        "icon": "https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/1f4c8.png",
        "sound": "minuet",
        "isArchive": "1"
    }

    try:
        logging.info("正在推送到 iPhone Bark...")
        res = requests.post(url, json=payload, timeout=15)
        if res.status_code == 200:
            logging.info("✅ 推送成功！请在 iPhone 上查看锁屏弹窗通知。")
        else:
            logging.error(f"❌ 推送失败，状态码: {res.status_code}, 内容: {res.text}")
    except Exception as e:
        logging.error(f"❌ 推送异常: {e}")
        sys.exit(1)


def main():
    today_str = datetime.now().strftime("%m月%d日")
    title = f"📊 全球财经与热点速递 ({today_str})"

    logging.info("开始拉取全球财经与热点数据...")
    news_data = fetch_news()

    logging.info("生成结构化摘要...")
    summary = generate_summary_with_ai(news_data)

    print("\n" + "=" * 40)
    print(f"{title}\n\n{summary}")
    print("=" * 40 + "\n")

    send_to_bark(title, summary)


if __name__ == "__main__":
    main()
