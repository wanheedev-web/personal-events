"""범용 수집기: 임의의 이벤트 목록 페이지에서 schema.org Event(JSON-LD)를 읽는다.

사이트 전용 수집기가 없는 URL(예: Eventbrite, 직접 추가한 출처)에 쓰입니다.
JSON-LD를 제공하지 않는 사이트는 0건이 나오며, 그 경우 전용 수집기가 필요합니다.
"""
from .common import event_id, is_vancouver, jsonld_events, page_details

MAX_DETAIL = 40  # 상세 페이지를 열어 보강할 최대 개수


def fetch(pw, src):
    browser = pw.chromium.launch()
    ctx = browser.new_context(
        geolocation={"latitude": 49.2827, "longitude": -123.1207},
        permissions=["geolocation"],
        timezone_id="America/Vancouver",
        locale="en-CA",
    )
    page = ctx.new_page()
    page.goto(src["url"], wait_until="networkidle", timeout=45000)
    for _ in range(3):
        page.mouse.wheel(0, 5000)
        page.wait_for_timeout(1000)

    found = {}
    for d in jsonld_events(page.content()):
        if d.get("url"):
            found[d["url"]] = d

    detail = ctx.new_page()
    for url, d in list(found.items())[:MAX_DETAIL]:
        if not d.get("start") or not d.get("description"):
            full = page_details(detail, url)
            for k, v in full.items():
                if v and not d.get(k):
                    d[k] = v
            detail.wait_for_timeout(800)
    browser.close()

    out = []
    for url, d in found.items():
        if not (d.get("title") and d.get("start")):
            continue
        if not is_vancouver(d.get("city"), d.get("region"), d.get("venue")):
            continue
        out.append({
            "id": event_id(url),
            "title": d["title"],
            "start": d["start"],
            "end": d.get("end"),
            "venue": d.get("venue") or "",
            "city": d.get("city") or "",
            "price_text": d.get("price_text") or "정보 없음",
            "is_free": bool(d.get("is_free")),
            "description": d.get("description") or "",
            "url": url,
            "source": src["id"],
        })
    print(f"[{src['id']}] {len(out)}개")
    return out
