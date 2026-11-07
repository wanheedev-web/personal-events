"""모든 출처를 수집 -> 기존 데이터와 병합 -> 요약 -> docs/events.json 저장.

실행: python -m src.build
"""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright

from . import generic, luma, notify, productbc
from .common import TZ

OUT = Path("docs/events.json")
OUT_JS = Path("docs/data.js")  # 파일로 직접 열어도 보이도록 같은 데이터를 JS로도 저장
SRC_FILE = Path("sources.json")
TYPES = {"luma": luma.fetch, "productbc": productbc.fetch, "generic": generic.fetch}
KEEP_PAST_DAYS = 90
SUMMARY_MODEL = "claude-haiku-5-5"


def load_existing():
    if OUT.exists():
        try:
            return json.loads(OUT.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"events": []}


def summarize(events):
    """설명이 있고 요약이 없는 이벤트만 Claude로 한국어 1~2문장 요약. 키가 없으면 앞부분 자르기."""
    client = None
    if os.environ.get("ANTHROPIC_API_KEY"):
        import anthropic

        client = anthropic.Anthropic()
    for e in events:
        if e.get("summary"):
            continue
        desc = (e.get("description") or "").strip()
        if not desc:
            e["summary"] = ""
            continue
        fallback = desc[:140] + ("…" if len(desc) > 140 else "")
        if not client:
            e["summary"] = fallback
            continue
        try:
            msg = client.messages.create(
                model=SUMMARY_MODEL,
                max_tokens=200,
                messages=[{
                    "role": "user",
                    "content": (
                        "아래 이벤트 설명을 한국어로 1~2문장(120자 내외)으로 요약해줘. "
                        "누구를 위한 행사인지, 무엇을 하는지만 담고, 고유명사는 원문 그대로 둬. "
                        "요약문만 출력해.\n\n제목: " + (e.get("title") or "") + "\n설명: " + desc[:3000]
                    ),
                }],
            )
            e["summary"] = msg.content[0].text.strip()
        except Exception as ex:
            print(f"요약 실패 ({e.get('title')}): {ex}")
            e["summary"] = fallback


def main():
    now = datetime.now(TZ)
    existing = load_existing()
    old = {e["id"]: e for e in existing.get("events", [])}

    sources = json.loads(SRC_FILE.read_text(encoding="utf-8"))["sources"]
    fresh, status = {}, {}
    with sync_playwright() as pw:
        for src in sources:
            sid = src["id"]
            if not src.get("enabled", True):
                status[sid] = {"ok": None, "count": 0}  # 수집 꺼짐
                continue
            fn = TYPES.get(src.get("type", "generic"), generic.fetch)
            try:
                items = fn(pw, src)
                status[sid] = {"ok": len(items) > 0, "count": len(items)}
            except Exception as ex:
                items = []
                status[sid] = {"ok": False, "count": 0, "error": str(ex)[:200]}
            for e in items:
                if e.get("title") and e.get("start"):
                    fresh[e["id"]] = e

    # 병합: 새로 수집한 것 + (수집 실패한 출처의 기존 것) + (등록된 출처의 최근 지난 이벤트 기록)
    merged = dict(fresh)
    failed_sources = {n for n, st in status.items() if st["ok"] is False}
    known = {src["id"] for src in sources}
    cutoff = now - timedelta(days=KEEP_PAST_DAYS)
    for eid, e in old.items():
        if eid in merged:
            continue
        start = datetime.fromisoformat(e["start"])
        is_past = start < now
        if e["source"] in failed_sources or (e["source"] in known and is_past and start > cutoff):
            merged[eid] = e

    for eid, e in merged.items():
        prev = old.get(eid, {})
        e["first_seen"] = prev.get("first_seen") or now.isoformat(timespec="minutes")
        if prev.get("summary") and prev.get("description") == e.get("description"):
            e["summary"] = prev["summary"]

    events = sorted(merged.values(), key=lambda e: e["start"])
    summarize(events)

    OUT.parent.mkdir(exist_ok=True)
    payload = {
        "generated_at": now.isoformat(timespec="minutes"),
        "sources": [{**src, **status[src["id"]]} for src in sources],
        "telegram": notify.check(),
        "events": events,
    }
    text = json.dumps(payload, ensure_ascii=False, indent=1)
    OUT.write_text(text, encoding="utf-8")
    OUT_JS.write_text("window.EVENTS_DATA = " + text + ";\n", encoding="utf-8")
    print(f"저장 완료: {len(events)}개, 상태: {status}")

    # 처음부터 한 번도 안 되던 출처나, 원래 행사가 없는 출처의 0건은 경고하지 않는다 (달력 화면에는 계속 표시됨)
    alert_sources = {
        n for n in failed_sources
        if status[n].get("error")
        or any(e["source"] == n and datetime.fromisoformat(e["start"]) >= now for e in old.values())
    }
    if alert_sources:
        detail = "\n".join(
            f"- {n}: {status[n].get('error', '이전에는 수집되던 출처가 0건')}" for n in sorted(alert_sources)
        )
        notify.send(f"⚠️ <b>이벤트 수집 문제</b>\n{detail}\n사이트 구조가 바뀌었을 수 있어요. Actions 로그를 확인하세요.")


if __name__ == "__main__":
    main()
