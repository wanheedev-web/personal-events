"""공통 유틸: 시간대, 벤쿠버 필터, JSON-LD 파서, 가격 표기."""
import hashlib
import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Vancouver")

# 'Vancouver'가 들어가면 통과 (North/West Vancouver 포함).
# 버나비, 리치먼드 등도 보고 싶으면 추가하세요: "burnaby", "richmond"
AREA_KEYWORDS = ("vancouver",)
EXCLUDE_KEYWORDS = ("washington", ", wa")


def is_vancouver(*texts):
    blob = " ".join(t or "" for t in texts).lower()
    if any(k in blob for k in EXCLUDE_KEYWORDS):
        return False
    return any(k in blob for k in AREA_KEYWORDS)


def event_id(url):
    return hashlib.sha1(url.split("?")[0].rstrip("/").encode()).hexdigest()[:12]


def to_local_iso(value):
    """ISO 문자열(오프셋 포함) 또는 'YYYY-MM-DD HH:MM:SS'(벤쿠버 현지) -> 벤쿠버 시각 ISO."""
    if not value:
        return None
    s = value.strip().replace("Z", "+00:00")
    if "T" not in s:
        s = s.replace(" ", "T", 1)
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    return dt.astimezone(TZ).isoformat(timespec="minutes")


def price_info(amount=None, currency="CAD", free=None, text=None):
    """(price_text, is_free)"""
    if text is not None:
        t = text.strip()
        if t == "" or t.lower() in ("free", "0", "$0", "무료"):
            return "Free", True
        return t, False
    if free:
        return "Free", True
    try:
        n = float(amount)
    except (TypeError, ValueError):
        return "정보 없음", False
    if n == 0:
        return "Free", True
    return f"${n:g} {currency or 'CAD'}", False


def _walk(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from _walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from _walk(v)


def jsonld_events(html):
    """페이지 안의 schema.org Event JSON-LD를 표준 dict 리스트로."""
    out = []
    pattern = r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>'
    for raw in re.findall(pattern, html, flags=re.S | re.I):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for node in _walk(data):
            t = node.get("@type")
            types = t if isinstance(t, list) else [t]
            if not any(isinstance(x, str) and x.endswith("Event") for x in types):
                continue
            loc = node.get("location") or {}
            if isinstance(loc, list):
                loc = loc[0] if loc else {}
            addr = loc.get("address") or {}
            if isinstance(addr, str):
                addr = {"streetAddress": addr}
            offers = node.get("offers") or {}
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            amount = offers.get("price", offers.get("lowPrice"))
            if amount is None:
                price_text, is_free = "정보 없음", False
            else:
                price_text, is_free = price_info(amount, offers.get("priceCurrency", "CAD"))
            out.append({
                "title": node.get("name"),
                "start": to_local_iso(node.get("startDate")),
                "end": to_local_iso(node.get("endDate")),
                "venue": ", ".join(x for x in [loc.get("name"), addr.get("streetAddress")] if x),
                "city": addr.get("addressLocality") or "",
                "region": addr.get("addressRegion") or "",
                "price_text": price_text,
                "is_free": is_free,
                "description": re.sub(r"\s+", " ", node.get("description") or "").strip(),
                "url": node.get("url"),
            })
    return out


def page_details(page, url):
    """이벤트 상세 페이지를 열어 JSON-LD에서 설명/가격/장소를 읽는다. 실패하면 {}."""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1500)
        found = jsonld_events(page.content())
        return found[0] if found else {}
    except Exception:
        return {}
