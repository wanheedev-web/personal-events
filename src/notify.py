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
