"""ProductBC 수집기.

1순위: 워드프레스 'The Events Calendar' REST API (플러그인을 쓰는 경우 가장 안정적).
2순위: Playwright로 /events/ 를 열어 JSON-LD 또는 외부 이벤트 링크(Luma/Eventbrite)를 수집.
어느 쪽이 실제로 동작하는지는 첫 실행 로그로 확인하세요.
"""
import re

import requests

from .common import event_id, jsonld_events, page_details, price_info, to_local_iso

BASE = "https://productbc.ca"
SOURCE = "productbc"
EXTERNAL = re.compile(r"https?://(?:lu\.ma|luma\.com|www\.eventbrite\.(?:ca|com))/[^\s\"'<>)]+")


def _strip(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).strip()


def _from_rest():
    r = requests.get(
        f"{BASE}/wp-json/tribe/events/v1/events",
        params={"per_page": 50, "start_date": "now"},
        timeout=20,
        headers={"User-Agent": "Mozilla/5.0 (personal event aggregator)"},
    )
    r.raise_for_status()
    out = []
    for ev in r.json().get("events", []):
        venue = ev.get("venue") or {}
        venue_text = ", ".join(x for x in [venue.get("venue"), venue.get("address"), venue.get("city")] if x)
        price_text, is_free = price_info(text=ev.get("cost") or "")
        out.append({
            "id": event_id(ev["url"]),
            "title": _strip(ev.get("title")),
            "start": to_local_iso(ev.get("start_date")),
            "end": to_local_iso(ev.get("end_date")),
            "venue": venue_text,
            "city": venue.get("city") or "Vancouver",
            "price_text": price_text if ev.get("cost") else "정보 없음",
            "is_free": is_free and bool(ev.get("cost")),
            "description": _strip(ev.get("description")),
            "url": ev["url"],
            "source": SOURCE,
        })
    return out


def _from_browser(pw):
    browser = pw.chromium.launch()
    ctx = browser.new_context(timezone_id="America/Vancouver", locale="en-CA")
    page = ctx.new_page()
    page.goto(f"{BASE}/events/", wait_until="networkidle", timeout=45000)
    html = page.content()
    found = {}
    for d in jsonld_events(html):
        if d.get("url") and d.get("start"):
            found[d["url"]] = d
    if not found:  # 외부 플랫폼 링크로 연결된 경우
        for link in dict.fromkeys(EXTERNAL.findall(html)):
            d = page_details(ctx.new_page(), link)
            if d.get("start"):
                d["url"] = d.get("url") or link
                found[d["url"]] = d
    browser.close()
    return [
        {
            "id": event_id(u),
            "title": d["title"],
            "start": d["start"],
            "end": d["end"],
            "venue": d["venue"],
            "city": d["city"] or "Vancouver",
            "price_text": d["price_text"],
            "is_free": d["is_free"],
            "description": d["description"],
            "url": u,
            "source": SOURCE,
        }
        for u, d in found.items()
    ]


def _tag(events, src):
    for e in events:
        e["source"] = src["id"]
    return events


def fetch(pw, src):
    try:
        events = _from_rest()
        if events:
            print(f"[{SOURCE}] REST API로 {len(events)}개")
            return _tag(events, src)
    except Exception as e:
        print(f"[{SOURCE}] REST 실패 ({e}), 브라우저로 재시도")
    events = _from_browser(pw)
    print(f"[{SOURCE}] 브라우저로 {len(events)}개")
    return _tag(events, src)
