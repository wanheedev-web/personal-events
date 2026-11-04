"""주간 텔레그램 알림: 앞으로 7일 안에 열리는 이벤트를 날짜별로 정리해 보냅니다.

실행: python -m src.digest
환경변수: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, SITE_URL(캘린더 페이지 주소, 선택)
"""
import html
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from . import notify
from .common import TZ

WEEKDAYS = "월화수목금토일"
DAYS_AHEAD = 7
LIMIT = 3900  # 텔레그램 메시지 한도 4096자 안쪽


def fmt_event(e):
    start = datetime.fromisoformat(e["start"])
    lines = [f'🕐 {start:%H:%M}  <a href="{html.escape(e["url"], quote=True)}">{html.escape(e["title"])}</a>']
    meta = []
    if e.get("venue"):
        meta.append("📍 " + html.escape(e["venue"][:70]))
    price = "무료" if e.get("is_free") else e.get("price_text", "")
    if price:
        meta.append("💲 " + html.escape(price))
    if meta:
        lines.append("   " + "  ".join(meta))
    if e.get("summary"):
        lines.append("   " + html.escape(e["summary"]))
    return "\n".join(lines)


def build_messages(events, now, site_url=""):
    end = now + timedelta(days=DAYS_AHEAD)
    upcoming = [e for e in events if now <= datetime.fromisoformat(e["start"]) < end]
    header = f"📅 <b>이번 주 벤쿠버 테크 이벤트</b> ({now:%m/%d} – {end - timedelta(days=1):%m/%d})\n"
    footer = f'\n🗓 <a href="{html.escape(site_url, quote=True)}">전체 캘린더 보기</a>' if site_url else ""

    if not upcoming:
        return [header + "\n예정된 이벤트가 없어요." + footer]

    blocks, current_day = [], None
    for e in upcoming:
        start = datetime.fromisoformat(e["start"])
        if start.date() != current_day:
            current_day = start.date()
            blocks.append(f"\n<b>{start:%m/%d} ({WEEKDAYS[start.weekday()]})</b>")
        blocks.append(fmt_event(e))

    messages, buf = [], header
    for b in blocks:
        if len(buf) + len(b) + 2 > LIMIT:
            messages.append(buf)
            buf = ""
        buf += "\n" + b
    messages.append(buf + footer)
    return messages


def main():
    data = json.loads(Path("docs/events.json").read_text(encoding="utf-8"))
    now = datetime.now(TZ)
    for msg in build_messages(data["events"], now, os.environ.get("SITE_URL", "")):
        notify.send(msg)


if __name__ == "__main__":
    main()
