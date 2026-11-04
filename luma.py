"""Luma 수집기.

Luma 목록 페이지는 JS로 그려지고, 이벤트 데이터는 내부 API 응답(JSON)으로 내려옵니다.
브라우저를 벤쿠버 위치/시간대로 열어 'Nearby Events'가 벤쿠버 기준으로 뜨게 하고,
오가는 JSON 응답을 가로채 이벤트를 모읍니다. 비공식 방식이라 Luma가 바꾸면 깨질 수 있습니다.
"""
from .common import event_id, is_vancouver, page_details, price_info, to_local_iso

def _walk(o):
    if isinstance(o, dict):
        ev = o.get("event")
        if isinstance(ev, dict) and ev.get("start_at") and ev.get("url"):
            yield o
        for v in o.values():
            yield from _walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from _walk(v)


def _collect(browser_ctx, url, bucket):
    page = browser_ctx.new_page()

    def on_response(resp):
        try:
            is_json = "json" in (resp.headers.get("content-type") or "")
            if is_json and ("lu.ma" in resp.url or "luma" in resp.url):
                bucket.append(resp.json())
        except Exception:
            pass

    page.on("response", on_response)
    page.goto(url, wait_until="networkidle", timeout=45000)
    for _ in range(6):  # 무한 스크롤 목록 더 불러오기
        page.mouse.wheel(0, 5000)
        page.wait_for_timeout(1200)
    page.close()


def fetch(pw, src):
    browser = pw.chromium.launch()
    ctx = browser.new_context(
        geolocation={"latitude": 49.2827, "longitude": -123.1207},
        permissions=["geolocation"],
        timezone_id="America/Vancouver",
        locale="en-CA",
    )
    events = {}
    for source, url in {src["id"]: src["url"]}.items():
        payloads = []
        try:
            _collect(ctx, url, payloads)
        except Exception as e:
            print(f"[{source}] 로딩 실패: {e}")
            continue
        for data in payloads:
            for entry in _walk(data):
                ev = entry["event"]
                geo = ev.get("geo_address_info") or {}
                city = geo.get("city_state") or geo.get("city") or ""
                full = geo.get("full_address") or geo.get("address") or ""
                if not is_vancouver(city, full):
                    continue
                link = "https://luma.com/" + str(ev["url"]).lstrip("/")
                ti = entry.get("ticket_info") or {}
                price_text, is_free = price_info(free=ti.get("is_free"))
                events[event_id(link)] = {
                    "id": event_id(link),
                    "title": ev.get("name"),
                    "start": to_local_iso(ev.get("start_at")),
                    "end": to_local_iso(ev.get("end_at")),
                    "venue": full or city,
                    "city": city,
                    "price_text": price_text,
                    "is_free": is_free,
                    "description": "",
                    "url": link,
                    "source": source,
                }
        print(f"[{source}] 누적 벤쿠버 이벤트 {len(events)}개")

    # 상세 페이지에서 설명/가격 보강
    page = ctx.new_page()
    for e in events.values():
        d = page_details(page, e["url"])
        if d.get("description"):
            e["description"] = d["description"]
        if d.get("price_text") and d["price_text"] != "정보 없음":
            e["price_text"], e["is_free"] = d["price_text"], d["is_free"]
        if d.get("venue") and not e["venue"]:
            e["venue"] = d["venue"]
        page.wait_for_timeout(800)  # 예의상 간격
    browser.close()
    return list(events.values())
