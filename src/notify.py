import os

import requests

API = "https://api.telegram.org/bot{token}/sendMessage"


def send(text, preview=False):
    """토큰이 없으면 콘솔에만 출력 (로컬 테스트용)."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("[telegram 미설정 - 콘솔 출력]\n" + text + "\n")
        return False
    r = requests.post(
        API.format(token=token),
        json={
            "chat_id": chat,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": not preview,
        },
        timeout=20,
    )
    r.raise_for_status()
    return True


def check():
    """텔레그램 연결 상태를 확인해 {"state": ...}로 반환. 토큰/chat id 값은 결과에 넣지 않는다.

    state: "ok"(연결됨) / "missing"(미설정) / "error"(설정은 했지만 확인 실패, reason에 이유)
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not token and not chat:
        return {"state": "missing"}
    if not token or not chat:
        code = "missing_token" if not token else "missing_chat"
        name = "TELEGRAM_BOT_TOKEN" if not token else "TELEGRAM_CHAT_ID"
        return {"state": "error", "code": code, "reason": f"{name} 값이 없어요"}
    base = f"https://api.telegram.org/bot{token}"
    try:  # 예외 메시지에는 토큰이 포함될 수 있어서 내용을 결과에 쓰지 않는다
        me = requests.get(f"{base}/getMe", timeout=15).json()
        if not me.get("ok"):
            return {"state": "error", "code": "token_invalid", "reason": "토큰이 올바르지 않아요"}
        ch = requests.get(f"{base}/getChat", params={"chat_id": chat}, timeout=15).json()
        if not ch.get("ok"):
            return {"state": "error", "code": "chat_invalid", "reason": "chat id가 틀렸거나 봇에게 /start를 보내지 않았어요"}
        return {"state": "ok"}
    except Exception:
        return {"state": "error", "code": "unreachable", "reason": "텔레그램에 접속하지 못했어요"}
