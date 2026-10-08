#!/usr/bin/env python3
"""
全球财经与综合热点深度早报推送脚本
- 深度覆盖：BBC、纽约时报、华尔街日报、全球权威财经与头条
- 新增：华语/好莱坞娱乐八卦与吃瓜猛料速递
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

# 优质公开新闻 RSS 源（覆盖 BBC、纽时、宏观财经、综合头条、以及娱乐吃瓜八卦）
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
    ],
    "吃瓜娱乐 / 明星八卦": [
        {"name": "华语吃瓜/星闻", "url": "https://news.google.com/rss/headlines/section/topic/ENTERTAINMENT?hl=zh-TW&gl=TW&ceid=TW:zh-Hant"},
        {"name": "内娱焦点", "url": "https://news.google.com/rss/headlines/section/topic/ENTERTAINMENT?hl=zh-CN&gl=CN&ceid=CN:zh-Hans"},
        {"name": "好莱坞/国际名流", "url": "https://news.google.com/rss/headlines/section/topic/ENTERTAINMENT?hl=en-US&gl=US&ceid=US:en"},
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

                    if title and not any(t["title"] == title for t in items):
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

    prompt = f"""你是一名资深主笔与全网资讯观察员。请根据以下今日抓取的 BBC、纽约时报、全球财经、国际头条与娱乐八卦，提炼出一份【兼具深度与趣味】的 iPhone 晨报。

排版模块要求：

📌【BBC & 纽约时报 深度国际要闻】
• 梳理 2~3 条重点大事件。包含【核心事件】+【具体细节/关键数据】+【地缘与各方影响】。

📈【全球宏观经济与市场动向】
• 梳理 2~3 条关键财经动向（美联储/央行政策、股市汇率、大宗商品等）。阐明数据与市场深层逻辑。

🌐【综合科技与产业焦点】
• 梳理 1~2 条全球热点或科技突破。

🍿【今日吃瓜·娱乐八卦速递】
• 梳理 2~3 条今日最具热度的华语及国际娱乐圈猛料、明星名人动态、情感纠葛或热搜吃瓜事件。语言风格生动、风趣幽默。

💡【今日主笔观察】
• 1~2 句话点出今日大势或市场前瞻。

排版要求：
- 条理分明，使用 Emoji 标签增强视觉层次。
- 内容充实有深度，八卦部分轻松风趣，全文约 800~1000 字左右。

原始新闻素材：
{raw_text}
"""

    # 1. 优先调用 Gemini API
    if gemini_key:
        try:
            logging.info("使用 Gemini API 进行深度要闻与八卦提炼...")
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
            logging.info("使用 OpenAI 兼容 API 进行深度提炼...")
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

    # 3. 兜底备选：无 Key 时的详尽排版
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
        "group": "全球早报·时政财经八卦",
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
    title = f"📰 今日早报：全球财经时政 & 吃瓜速递 ({today_str})"

    logging.info("开始多源抓取 BBC、纽时、全球财经与娱乐八卦...")
    news_data = fetch_news()

    logging.info("提炼内容...")
    summary = generate_detailed_summary(news_data)

    print("\n" + "=" * 45)
    print(f"{title}\n\n{summary}")
    print("=" * 45 + "\n")

    send_to_bark(title, summary)


if __name__ == "__main__":
    main()
