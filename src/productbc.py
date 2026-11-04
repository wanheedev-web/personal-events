"""ProductBC 수집기 (v2).

productbc.ca/events/ 는 껍데기이고, 실제 이벤트는 아래 두 곳에 있습니다.
  1) tightknit 임베드 캘린더 (JS로 그려짐)
  2) Eventbrite ProductBC 주최자 페이지
두 페이지를 브라우저로 열어 '개별 이벤트 링크'를 모은 뒤, 각 이벤트 페이지(JSON-LD)에서
날짜/장소/가격/설명을 읽습니다. 구조를 확정하기 어려워 로그에 진단 정보를 많이 남깁니다.
"""
import re
from datetime import datetime, timedelta

from .common import TZ, event_id, jsonld_events, page_details

PAGES = [
    "https://productbc.tightknit.community/embed/events?display-calendar-filters=true",
    "https://www.eventbrite.ca/o/productbc-80996805383",
]
HREF = re.compile(r"""href=["'](https?://[^"'#\s]+)""")
LUMA_SKIP = {"discover", "calendar", "home", "signin", "explore", "events", "about", "pricing", "help", "create"}
MAX_DETAIL = 30


def _is_event_link(url):
    u = url.split("?")[0].rstrip("/")
    if re.search(r"eventbrite\.[a-z.]+/e/", u):
        return True
    m = re.search(r"(?:luma\.com|lu\.ma)/([A-Za-z0-9_-]+)$", u)
    if m and m.group(1).lower() not in LUMA_SKIP:
        return True
    if "tightknit.community" in u and re.search(r"/events?/[^/]+", u):
        return True
    return False


def _collect(ctx, url):
    """페이지를 열어 (JSON-LD 이벤트들, 이벤트 링크들)을 반환하고 진단 로그를 남긴다."""
    page = ctx.new_page()
    api_seen = []

    def on_response(resp):
        try:
            if "json" in (resp.headers.get("content-type") or "") and "tightknit" in resp.url:
                api_seen.append(resp.url)
        except Exception:
            pass

    page.on("response", on_response)
    page.goto(url, wait_until="networkidle", timeout=45000)
    for _ in range(4):
        page.mouse.wheel(0, 5000)
        page.wait_for_timeout(1000)
    html = page.content()
    page.close()

    ld = [d for d in jsonld_events(html) if d.get("url") and d.get("start")]
    links = list(dict.fromkeys(u.split("?")[0] for u in HREF.findall(html) if _is_event_link(u)))
    print(f"[productbc] {url}")
    print(f"  JSON-LD 이벤트 {len(ld)}개 / 이벤트 링크 {len(links)}개 / 화면 크기 {len(html)}자")
    for u in links[:5]:
        print("  링크 예:", u)
    for u in api_seen[:5]:
        print("  tightknit JSON 응답:", u)
    return ld, links


def fetch(pw, src):
    browser = pw.chromium.launch()
    ctx = browser.new_context(timezone_id="America/Vancouver", locale="en-CA")
    found = {}
    pending = []
    for url in PAGES:
        try:
            ld, links = _collect(ctx, url)
        except Exception as e:
            print(f"[productbc] 열기 실패 {url}: {e}")
            continue
        for d in ld:
            found[d["url"].split("?")[0]] = d
        pending += [u for u in links if u not in found]

    detail = ctx.new_page()
    for link in list(dict.fromkeys(pending))[:MAX_DETAIL]:
        d = page_details(detail, link)
        if d.get("title") and d.get("start"):
            d["url"] = link
            found[link] = d
        else:
            print("  상세 읽기 실패(JSON-LD 없음):", link)
        detail.wait_for_timeout(800)
    browser.close()

    cutoff = datetime.now(TZ) - timedelta(days=1)
    out = []
    for url, d in found.items():
        if datetime.fromisoformat(d["start"]) < cutoff:
            continue  # 이미 지난 행사는 제외
        out.append({
            "id": event_id(url),
            "title": d["title"],
            "start": d["start"],
            "end": d.get("end"),
            "venue": d.get("venue") or "",
            "city": d.get("city") or "Vancouver",
            "price_text": d.get("price_text") or "정보 없음",
            "is_free": bool(d.get("is_free")),
            "description": d.get("description") or "",
            "url": url,
            "source": src["id"],
        })
    print(f"[productbc] 최종 {len(out)}개")
    return out
