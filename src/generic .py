"""범용 수집기: 임의의 이벤트 목록 페이지에서 이벤트를 모은다.

1) 페이지 안의 schema.org Event(JSON-LD)를 읽는다.
2) 없으면(예: Eventbrite 검색 페이지) 개별 이벤트 링크(/e/...)를 모아 각 이벤트 페이지를 열어
   날짜/장소/비용/설명을 읽는다.
Eventbrite 검색(/d/...) 주소는 앞쪽 몇 페이지(?page=2, 3)까지 읽는다.
"""
import re

from .common import event_id, is_vancouver, jsonld_events, page_details

MAX_PAGES = 3      # Eventbrite 검색 결과를 몇 페이지까지 읽을지
MAX_DETAIL = 40    # 상세 페이지를 열어볼 최대 개수 (너무 많으면 느리고 차단 위험)
HREF = re.compile(r"""href=["'](https?://[^"'#\s]+)""")
EB_EVENT = re.compile(r"^https?://(?:www\.)?eventbrite\.[a-z.]+/e/[^/?]*?(\d{6,})(?:[/?]|$)")


def _eb_links(urls):
    """Eventbrite 개별 이벤트 링크를 숫자 id 기준으로 중복 제거해 {id: 깨끗한 URL}로 반환."""
    out = {}
    for u in urls:
        m = EB_EVENT.match(u)
        if m and m.group(1) not in out:
            out[m.group(1)] = u.split("?")[0]
    return out


def _page_urls(url):
    if "eventbrite." in url and "/d/" in url:
        base = url.split("?")[0].rstrip("/") + "/"
        return [base] + [f"{base}?page={n}" for n in range(2, MAX_PAGES + 1)]
    return [url]


def fetch(pw, src):
    browser = pw.chromium.launch()
    ctx = browser.new_context(
        geolocation={"latitude": 49.2827, "longitude": -123.1207},
        permissions=["geolocation"],
        timezone_id="America/Vancouver",
        locale="en-CA",
    )
    found, links = {}, {}
    for url in _page_urls(src["url"]):
        try:
            page = ctx.new_page()
            page.goto(url, wait_until="networkidle", timeout=45000)
            try:  # 이벤트 카드가 그려질 때까지 잠깐 기다림 (없으면 그냥 진행)
                page.wait_for_selector('a[href*="/e/"]', timeout=8000)
            except Exception:
                pass
            for _ in range(3):
                page.mouse.wheel(0, 5000)
                page.wait_for_timeout(1000)
            html = page.content()
            hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
            try:
                title = page.title()
                body = " ".join(page.inner_text("body").split())[:160]
            except Exception:
                title, body = "?", "?"
            page.close()
        except Exception as e:
            print(f"[{src['id']}] 열기 실패 {url}: {e}")
            continue
        ld = [d for d in jsonld_events(html) if d.get("url")]
        eb = _eb_links(list(hrefs) + HREF.findall(html))
        print(f"[{src['id']}] {url}")
        print(f"  제목: {title} / HTML {len(html)}자 / a링크 {len(hrefs)}개 / JSON-LD {len(ld)}개 / Eventbrite 링크 {len(eb)}개")
        print(f"  화면 글자: {body}")
        for d in ld:
            found[d["url"].split("?")[0]] = d
        links.update({k: v for k, v in eb.items() if k not in links})

    # 목록에 상세가 부족한 항목 + 링크만 있는 항목은 상세 페이지에서 읽는다
    detail = ctx.new_page()
    todo = [u for u in links.values() if u not in found][:MAX_DETAIL]
    for d in list(found.values()):
        if not d.get("start") and d.get("url"):
            todo.append(d["url"])
    ok = bad = 0
    for link in todo:
        d = page_details(detail, link)
        if d.get("title") and d.get("start"):
            d["url"] = link
            found[link] = d
            ok += 1
        else:
            bad += 1
            if bad <= 3:
                print("  상세 읽기 실패:", link)
        detail.wait_for_timeout(800)
    browser.close()
    if todo:
        print(f"[{src['id']}] 상세 페이지 성공 {ok} / 실패 {bad}")

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
    print(f"[{src['id']}] 벤쿠버 이벤트 최종 {len(out)}개")
    return out
