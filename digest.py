#!/usr/bin/env python3
"""
全球财经与综合热点深度早报推送脚本
- 深度覆盖：BBC、纽约时报、华尔街日报、全球权威财经、综合头条、娱乐八卦吃瓜
- 自动生成移动端专属【大字版沉浸式网页】(index.html)，自动发布至 GitHub Pages
- Bark 推送横幅自带网页跳转链接，点击即以大字号舒适阅读全文
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

PAGES_URL = "https://ding-hello.github.io/global-finance-digest/"

# 优质公开新闻 RSS 源
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
    """智能提纯摘要，避免重复标题"""
    if not raw_summary:
        return ""
    clean_t = title.split(" - ")[0].strip()
    s = raw_summary
    if clean_t and clean_t in s:
        s = s.replace(clean_t, "").strip()

    s = re.sub(r"(前往\s*Google\s*新聞.*|前往\s*Google\s*新闻.*|View Full Coverage on Google News.*)", "", s, flags=re.IGNORECASE).strip()
    s = re.sub(r"^[：:,\-\|\s]+", "", s).strip()

    if len(s) < 12:
        return ""

    return s[:120] + "..." if len(s) > 120 else s


def fetch_news(max_per_feed=2):
    """抓取各分类新闻并全局去重"""
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

                    title_fingerprint = clean_title[:12].lower()
                    if clean_title and title_fingerprint not in seen_titles:
                        seen_titles.add(title_fingerprint)
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


def generate_html_page(news_data, date_str, period_str):
    """生成移动端大字号自适应沉浸阅读网页 (index.html)"""
    category_meta = {
        "BBC / 纽约时报 国际深度": {"icon": "📌", "desc": "全球重大地缘时政与深度调查"},
        "全球财经 / 宏观市场": {"icon": "📈", "desc": "美联储、全球股市、外汇大宗商品"},
        "全球综合焦点头条": {"icon": "🌐", "desc": "全球科技变革与重磅突发要闻"},
        "吃瓜娱乐 / 明星八卦": {"icon": "🍿", "desc": "华语及好莱坞一线大瓜与名流八卦"}
    }

    cards_html = ""
    for cat, items in news_data.items():
        meta = category_meta.get(cat, {"icon": "🔹", "desc": ""})
        items_html = ""
        for item in items[:3]:
            summary_html = f'<p class="news-summary">{item["summary"]}</p>' if item['summary'] else ""
            link_html = f'<a href="{item["link"]}" target="_blank" class="news-link">查看原报道 ↗</a>' if item.get('link') else ""
            items_html += f"""
            <div class="news-item">
                <div class="news-meta">
                    <span class="source-badge">{item['source']}</span>
                </div>
                <h3 class="news-title">{item['title']}</h3>
                {summary_html}
                {link_html}
            </div>
            """

        cards_html += f"""
        <section class="card">
            <div class="card-header">
                <span class="card-icon">{meta['icon']}</span>
                <div>
                    <h2>{cat}</h2>
                    <span class="card-sub">{meta['desc']}</span>
                </div>
            </div>
            <div class="news-list">
                {items_html}
            </div>
        </section>
        """

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>📰 今日{period_str} · 全球时政财经与热点速递</title>
    <style>
        :root {{
            --bg-color: #f7f9fa;
            --card-bg: #ffffff;
            --text-main: #1a1a1a;
            --text-sub: #555555;
            --text-muted: #888888;
            --accent: #2563eb;
            --border-color: #e5e7eb;
            --badge-bg: #eff6ff;
            --badge-color: #1d4ed8;
        }}
        @media (prefers-color-scheme: dark) {{
            :root {{
                --bg-color: #0f172a;
                --card-bg: #1e293b;
                --text-main: #f8fafc;
                --text-sub: #cbd5e1;
                --text-muted: #94a3b8;
                --accent: #38bdf8;
                --border-color: #334155;
                --badge-bg: #1e3a5f;
                --badge-color: #7dd3fc;
            }}
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
            background-color: var(--bg-color);
            color: var(--text-main);
            padding: 16px;
            max-width: 680px;
            margin: 0 auto;
            line-height: 1.6;
            -webkit-font-smoothing: antialiased;
        }}
        header {{
            padding: 24px 8px 16px;
            text-align: left;
        }}
        .header-tag {{
            font-size: 14px;
            color: var(--accent);
            font-weight: 700;
            letter-spacing: 1px;
            text-transform: uppercase;
        }}
        h1 {{
            font-size: 28px;
            font-weight: 800;
            margin: 8px 0;
            line-height: 1.25;
        }}
        .update-time {{
            font-size: 15px;
            color: var(--text-muted);
        }}
        .card {{
            background: var(--card-bg);
            border-radius: 16px;
            padding: 20px 18px;
            margin-bottom: 20px;
            box-shadow: 0 4px 16px rgba(0,0,0,0.04);
            border: 1px solid var(--border-color);
        }}
        .card-header {{
            display: flex;
            align-items: center;
            gap: 12px;
            padding-bottom: 14px;
            border-bottom: 1.5px solid var(--border-color);
            margin-bottom: 16px;
        }}
        .card-icon {{
            font-size: 28px;
        }}
        .card-header h2 {{
            font-size: 21px;
            font-weight: 700;
        }}
        .card-sub {{
            font-size: 13px;
            color: var(--text-muted);
            display: block;
        }}
        .news-item {{
            padding: 14px 0;
            border-bottom: 1px dashed var(--border-color);
        }}
        .news-item:last-child {{
            border-bottom: none;
            padding-bottom: 0;
        }}
        .news-meta {{
            margin-bottom: 6px;
        }}
        .source-badge {{
            font-size: 12px;
            font-weight: 600;
            padding: 3px 8px;
            background: var(--badge-bg);
            color: var(--badge-color);
            border-radius: 6px;
        }}
        .news-title {{
            font-size: 20px;
            font-weight: 700;
            line-height: 1.45;
            color: var(--text-main);
            margin-bottom: 8px;
        }}
        .news-summary {{
            font-size: 17px;
            color: var(--text-sub);
            line-height: 1.6;
            margin-bottom: 8px;
        }}
        .news-link {{
            font-size: 14px;
            color: var(--accent);
            text-decoration: none;
            font-weight: 500;
            display: inline-block;
        }}
        footer {{
            text-align: center;
            padding: 28px 0 40px;
            color: var(--text-muted);
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <header>
        <span class="header-tag">DAILY INTELLIGENCE</span>
        <h1>📰 今日{period_str}速递</h1>
        <div class="update-time">📅 {date_str} · 全球大势与精选吃瓜</div>
    </header>

    {cards_html}

    <footer>
        <p>由 GitHub Actions 云端自动驱动生成 · 点击原报道可阅读深度全文</p>
    </footer>
</body>
</html>
"""
    os.makedirs("public", exist_ok=True)
    with open("public/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    logging.info("✅ 成功生成移动端大字号专属网页 public/index.html")


def generate_compact_notification_text(news_data):
    """为手机锁屏横幅生成清爽、字号大、带跳转提示的精炼概览"""
    lines = []
    category_icons = {
        "BBC / 纽约时报 国际深度": "📌",
        "全球财经 / 宏观市场": "📈",
        "全球综合焦点头条": "🌐",
        "吃瓜娱乐 / 明星八卦": "🍿"
    }

    for cat, items in news_data.items():
        if items:
            icon = category_icons.get(cat, "🔹")
            first_title = items[0]['title'].split(" - ")[0].strip()
            lines.append(f"{icon} {first_title}")

    lines.append("\n👉 点击本通知直达大字版网页全文阅读")
    return "\n".join(lines).strip()


def send_to_bark(title, body, url=PAGES_URL):
    """通过 Bark 推送到 iPhone，支持点击打开大字版网页"""
    bark_key = os.getenv("BARK_KEY")
    bark_server = os.getenv("BARK_SERVER", "https://api.day.app")

    if not bark_key:
        logging.error("未找到 BARK_KEY 环境变量！请在 GitHub Secrets 中配置 BARK_KEY。")
        sys.exit(1)

    payload = {
        "title": title,
        "body": body,
        "url": url,  # 点击通知直接打开该网页
        "group": "全球早报·时政财经八卦",
        "icon": "https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/1f4f0.png",
        "sound": "minuet",
        "isArchive": "1"
    }

    post_url = f"{bark_server.rstrip('/')}/{bark_key}/"
    try:
        logging.info(f"正在推送到 iPhone Bark (携带大字版跳转链接: {url})...")
        res = requests.post(post_url, json=payload, timeout=20)
        if res.status_code == 200:
            logging.info("✅ 推送成功！请在 iPhone 查看锁屏弹窗，点击即可进入大字版！")
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

    logging.info("生成手机端大字号专属网页...")
    generate_html_page(news_data, now.strftime("%Y年%m月%d日"), period)

    logging.info("生成锁屏通知精炼内容...")
    compact_body = generate_compact_notification_text(news_data)

    print("\n" + "=" * 45)
    print(f"{title}\n\n{compact_body}")
    print("=" * 45 + "\n")

    send_to_bark(title, compact_body, url=PAGES_URL)


if __name__ == "__main__":
    main()
