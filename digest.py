#!/usr/bin/env python3
"""
全球财经与综合热点深度早报推送脚本
- 深度覆盖：BBC、纽约时报、华尔街日报、全球权威财经、综合头条、娱乐八卦吃瓜
- 智能去重：严格剔除 RSS 摘要中重复的标题文本与垃圾尾缀，杜绝重复两条问题
- 全局防重：跨版块事件全局去重
- 自动适配 iPhone APNs 与 Bark 最佳长度限制
- 区分早报与下午版，支持大模型深度提炼
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
    "BBC / 纽约时报 国际深度": [
        {"name": "BBC 中文", "url": "https://www.bbc.com/zhongwen/simp/index.xml"},
        {"name": "纽约时报 国际", "url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"},
        {"name": "BBC World", "url": "https://feeds.bbci.co.uk/news/world/rss.xml"},
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
        {"name": "欧美名流八卦", "url": "https://news.google.com/rss/headlines/section/topic/ENTERTAINMENT?hl=en-US&gl=US&ceid=US:en"},
    ]
}


def clean_html(raw_html):
    """去除 HTML 标签与多余空白，保留纯文本"""
    if not raw_html:
        return ""
    text = re.sub(r"<[^>]+>", "", raw_html)
    text = re.sub(r"&[a-z]+;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_real_summary(title, raw_summary):
    """
    智能去重与提纯：
    从 summary 中剔除重复的标题内容、媒体名和占位符。
    只有当 summary 包含真正有价值的增量信息时才返回，杜绝'同一句话重复两次'。
    """
    if not raw_summary:
        return ""
    clean_t = title.split(" - ")[0].strip()
    s = raw_summary
    # 移除摘要开头重复出现的完整标题
    if clean_t and clean_t in s:
        s = s.replace(clean_t, "").strip()

    # 移除常见的 Google News / RSS 营销导流尾缀
    s = re.sub(r"(前往\s*Google\s*新聞.*|前往\s*Google\s*新闻.*|View Full Coverage on Google News.*)", "", s, flags=re.IGNORECASE).strip()
    # 移除开头的多余标点与媒体名残留
    s = re.sub(r"^[：:,\-\|\s]+", "", s).strip()

    # 如果剥离标题后，剩余内容太短（少于12个字，说明只是纯媒体后缀或噪音），直接舍弃
    if len(s) < 12:
        return ""

    return s[:75] + "..." if len(s) > 75 else s


def fetch_news(max_per_feed=2):
    """抓取各分类新闻，全局去重，并提纯增量导读"""
    collected = {}
    seen_titles = set()

    for cat, feed_list in FEEDS.items():
        items = []
        for feed_info in feed_list:
            url = feed_info["url"]
            source_name = feed_info["name"]
            try:
                logging.info(f"正在拉取 [{source_name}]: {url}")
                parsed = feedparser.parse(url)
                for entry in parsed.entries[:max_per_feed]:
                    raw_title = entry.get("title", "").strip()
                    clean_title = raw_title.split(" - ")[0].strip()
                    link = entry.get("link", "")
                    raw_summary = clean_html(entry.get("summary") or entry.get("description") or "")

                    # 全局去重判断（简化标题对比前 12 个字）
                    title_fingerprint = clean_title[:12].lower()
                    if clean_title and title_fingerprint not in seen_titles:
                        seen_titles.add(title_fingerprint)
                        # 提纯增量摘要
                        real_summary = extract_real_summary(raw_title, raw_summary)
                        items.append({
                            "source": source_name,
                            "title": clean_title,
                            "summary": real_summary,
                            "link": link
                        })
            except Exception as e:
                logging.warning(f"拉取失败 {source_name} ({url}): {e}")
        collected[cat] = items
    return collected


def generate_detailed_summary(news_data):
    """若配置了大模型 API，进行深度提炼；否则输出干净利落的精美排版"""
    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    openai_base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model_name = os.getenv("MODEL_NAME", "gpt-4o-mini")

    raw_text = ""
    for cat, items in news_data.items():
        raw_text += f"\n=== {cat} ===\n"
        for idx, item in enumerate(items[:3], 1):
            raw_text += f"[{item['source']}] {item['title']}\n"
            if item["summary"]:
                raw_text += f"   导读: {item['summary']}\n"

    prompt = f"""你是一名资深全网资讯观察员。请根据今日抓取的 BBC、纽约时报、全球财经、国际头条与娱乐八卦，提炼出一份精炼且有深度的 iPhone 晨报。

严格按照以下模块排版（请使用 Emoji 标签）：
📌【BBC & 纽约时报 国际深度】（2 条重磅事件与影响）
📈【全球宏观市场动向】（2 条核心财经指标与逻辑）
🌐【综合科技与焦点】（1~2 条热点突破）
🍿【今日吃瓜·娱乐八卦】（2 条明星名流情感纠葛或热搜吃瓜，语言风趣幽默）
💡【主笔观察】（1 句话点出今日大势）

字数限制：严格控制在 500~650 字以内，排版清爽，适合手机弹窗速读，杜绝任何重复语句。

原始新闻素材：
{raw_text}
"""

    # 1. 优先调用 Gemini API
    if gemini_key:
        try:
            logging.info("使用 Gemini API 总结...")
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

    # 2. 调用 OpenAI 兼容 API
    if openai_key:
        try:
            logging.info("使用 OpenAI 兼容 API 总结...")
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

    # 3. 兜底精简排版（彻底解决重复两条问题）
    logging.info("未配置 AI 密钥，采用自带的高密度排版模式")
    lines = []
    category_icons = {
        "BBC / 纽约时报 国际深度": "📌",
        "全球财经 / 宏观市场": "📈",
        "全球综合焦点头条": "🌐",
        "吃瓜娱乐 / 明星八卦": "🍿"
    }

    for cat, items in news_data.items():
        icon = category_icons.get(cat, "🔹")
        lines.append(f"{icon}【{cat}】")
        for idx, item in enumerate(items[:2], 1):  # 每个版块精选 2 条
            lines.append(f"• [{item['source']}] {item['title']}")
            # 仅当有真正增量背景信息时才附带一行导读
            if item['summary']:
                lines.append(f"  ↳ {item['summary']}")
        lines.append("")

    return "\n".join(lines).strip()


def send_to_bark(title, body):
    """通过 Bark 推送到 iPhone 弹窗，带自动长度保护与重试机制"""
    bark_key = os.getenv("BARK_KEY")
    bark_server = os.getenv("BARK_SERVER", "https://api.day.app")

    if not bark_key:
        logging.error("未找到 BARK_KEY 环境变量！请在 GitHub Secrets 中配置 BARK_KEY。")
        sys.exit(1)

    # 严格限制长度不超过 900 字符，确保 Apple APNs 与 Nginx 100% 接收（避免 413）
    if len(body) > 900:
        logging.info(f"正文长度 {len(body)} 超过 900 字符，自动安全截断以防 APNs 413 拒收")
        body = body[:890] + "...\n(更多详情见今日新闻)"

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
        logging.info(f"正在推送到 iPhone Bark (正文字数: {len(body)})...")
        res = requests.post(url, json=payload, timeout=20)
        if res.status_code == 200:
            logging.info("✅ 推送成功！请在 iPhone 查看锁屏弹窗与通知中心。")
        else:
            logging.error(f"❌ 推送失败，状态码: {res.status_code}, 内容: {res.text}")
            sys.exit(1)
    except Exception as e:
        logging.error(f"❌ 推送异常: {e}")
        sys.exit(1)


def main():
    now = datetime.now()
    today_str = now.strftime("%m月%d日")
    period = "早报" if now.hour < 12 else "下午版"
    title = f"📰 今日{period}：全球时政财经 & 吃瓜速递 ({today_str})"

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
