#!/usr/bin/env python3
"""
全球财经与综合热点深度早报推送脚本
- 深度覆盖：BBC、纽约时报 (The New York Times)、华尔街日报、全球权威财经与头条
- 提取新闻完整摘要（导语/背景），提供更详尽的深度信息
- 支持大模型 (Gemini / OpenAI / DeepSeek) 智能深度提炼与脉络剖析
- 通过 Bark 推送到 iPhone 锁屏弹窗
"""

import os
import sys
import re
import json
import logging
from datetime import datetime
import feedparser
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# 优质公开新闻 RSS 源（重点覆盖 BBC、纽约时报、全球财经与综合热点）
FEEDS = {
    "BBC / 纽约时报 国际热点": [
        {"name": "BBC 中文", "url": "https://www.bbc.com/zhongwen/simp/index.xml"},
        {"name": "BBC World", "url": "https://feeds.bbci.co.uk/news/world/rss.xml"},
        {"name": "纽约时报 国际", "url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"},
        {"name": "纽约时报 商业", "url": "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml"},
    ],
    "全球财经 / 宏观市场": [
        {"name": "华尔街日报 WSJ", "url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"},
        {"name": "谷歌财经(中文)", "url": "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=zh-CN&gl=CN&ceid=CN:zh-Hans"},
        {"name": "谷歌财经(全球)", "url": "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-US&gl=US&ceid=US:en"},
    ],
    "全球综合焦点头条": [
        {"name": "全球头条(中文)", "url": "https://news.google.com/rss?hl=zh-CN&gl=CN&ceid=CN:zh-Hans"},
        {"name": "全球头条(国际)", "url": "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"},
    ]
}


def clean_html(raw_html):
    """去除 HTML 标签与多余空白，保留纯文本摘要"""
    if not raw_html:
        return ""
    text = re.sub(r"<[^>]+>", "", raw_html)
    text = re.sub(r"&[a-z]+;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fetch_news(max_per_feed=3):
    """抓取各分类新闻，包含标题与正文导语摘要"""
    collected = {}
    for cat, feed_list in FEEDS.items():
        items = []
        for feed_info in feed_list:
            url = feed_info["url"]
            source_name = feed_info["name"]
            try:
                logging.info(f"正在拉取 [{source_name}]: {url}")
                parsed = feedparser.parse(url)
                for entry in parsed.entries[:max_per_feed]:
                    title = entry.get("title", "").strip()
                    summary = clean_html(entry.get("summary") or entry.get("description") or "")
                    link = entry.get("link", "")

                    # 简单去重
                    if title and not any(t["title"] == title for t in items):
                        # 过滤无意义的超短摘要
                        if len(summary) > 200:
                            summary = summary[:200] + "..."
                        items.append({
                            "source": source_name,
                            "title": title,
                            "summary": summary,
                            "link": link
                        })
            except Exception as e:
                logging.warning(f"拉取失败 {source_name} ({url}): {e}")
        collected[cat] = items
    return collected


def generate_detailed_summary(news_data):
    """若配置了大模型 API，进行深度详尽提炼；否则输出丰富结构化图文排版"""
    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    openai_base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model_name = os.getenv("MODEL_NAME", "gpt-4o-mini")

    raw_text = ""
    for cat, items in news_data.items():
        raw_text += f"\n=== {cat} ===\n"
        for idx, item in enumerate(items, 1):
            raw_text += f"[{item['source']}] {item['title']}\n"
            if item["summary"]:
                raw_text += f"   详情导读: {item['summary']}\n"

    prompt = f"""你是一名资深国际政治与宏观经济主笔。请根据以下今日抓取的 BBC、纽约时报、全球财经与头条新闻，提炼出一份【内容详尽、富有深度】的 iPhone 晨报。

用户希望看到详尽具体的事实与背景，请拒绝空洞概括，严格按照以下模块排版：

📌【BBC & 纽约时报 深度国际要闻】
• 梳理 2~3 条重点大事件。每条列出：【核心事件】+【事件背景/具体细节与关键数据】+【各方态度或地缘影响】。

📈【全球宏观经济与市场动向】
• 梳理 2~3 条关键财经动向（美联储/货币政策、大宗商品、股市汇率等）。阐述具体数据变动与市场深层逻辑。

🌐【综合科技与重磅焦点】
• 梳理 1~2 条全球热点或科技产业突破事件，阐明核心影响。

💡【今日主笔观察】
• 用 1~2 段话对今日全球大势进行一针见血的总结与前瞻。

排版要求：
- 条理清晰，使用表情符号（Emoji）增强可读性。
- 内容要充实、有事实支撑，字数适度扩充至 700~900 字左右，方便在手机屏幕上获得充足信息量。

原始新闻素材：
{raw_text}
"""

    # 1. 优先调用 Gemini API
    if gemini_key:
        try:
            logging.info("使用 Gemini API 进行深度要闻提炼...")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            res = requests.post(url, json=payload, timeout=35)
            if res.status_code == 200:
                data = res.json()
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()
            else:
                logging.warning(f"Gemini API 响应异常: {res.text}")
        except Exception as e:
            logging.warning(f"Gemini API 调用出错: {e}")

    # 2. 调用 OpenAI 兼容 API (如 DeepSeek / OpenAI)
    if openai_key:
        try:
            logging.info("使用 OpenAI 兼容 API 进行深度要闻提炼...")
            headers = {"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"}
            payload = {
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.5
            }
            res = requests.post(f"{openai_base}/chat/completions", headers=headers, json=payload, timeout=35)
            if res.status_code == 200:
                data = res.json()
                return data["choices"][0]["message"]["content"].strip()
            else:
                logging.warning(f"OpenAI API 响应异常: {res.text}")
        except Exception as e:
            logging.warning(f"OpenAI API 调用出错: {e}")

    # 3. 兜底备选：无 Key 时的详尽排版（带背景导读）
    logging.info("未配置 AI 密钥，采用自带的高密度详尽排版模式")
    lines = []
    for cat, items in news_data.items():
        lines.append(f"━━━━━━━━━━\n【{cat}】\n━━━━━━━━━━")
        for idx, item in enumerate(items[:4], 1):
            title = item['title'].split(" - ")[0]
            lines.append(f"🔹 [{item['source']}] {title}")
            if item['summary']:
                lines.append(f"   ↳ {item['summary']}")
            lines.append("")
    return "\n".join(lines).strip()


def send_to_bark(title, body):
    """通过 Bark 推送到 iPhone 弹窗"""
    bark_key = os.getenv("BARK_KEY")
    bark_server = os.getenv("BARK_SERVER", "https://api.day.app")

    if not bark_key:
        logging.error("未找到 BARK_KEY 环境变量！请在 GitHub Secrets 中配置 BARK_KEY。")
        sys.exit(1)

    url = f"{bark_server.rstrip('/')}/{bark_key}/"
    payload = {
        "title": title,
        "body": body,
        "group": "全球早报·深度速递",
        "icon": "https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/1f4f0.png",
        "sound": "minuet",
        "isArchive": "1"
    }

    try:
        logging.info("正在推送到 iPhone Bark...")
        res = requests.post(url, json=payload, timeout=20)
        if res.status_code == 200:
            logging.info("✅ 推送成功！请在 iPhone 查看锁屏弹窗与通知中心。")
        else:
            logging.error(f"❌ 推送失败，状态码: {res.status_code}, 内容: {res.text}")
    except Exception as e:
        logging.error(f"❌ 推送异常: {e}")
        sys.exit(1)


def main():
    today_str = datetime.now().strftime("%m月%d日")
    title = f"📰 深度早报：BBC/纽时/全球财经 ({today_str})"

    logging.info("开始多源抓取 BBC、纽时、全球财经与焦点新闻...")
    news_data = fetch_news()

    logging.info("提炼深度要闻内容...")
    summary = generate_detailed_summary(news_data)

    print("\n" + "=" * 45)
    print(f"{title}\n\n{summary}")
    print("=" * 45 + "\n")

    send_to_bark(title, summary)


if __name__ == "__main__":
    main()
