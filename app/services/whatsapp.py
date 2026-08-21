"""
Thin wrapper around Meta's WhatsApp Cloud API.
Two message types used throughout the bot:
  - plain text (send_text)
  - interactive list messages (send_list) - used for subject menu and
    answer options, since list messages handle 4+ options cleanly
    (buttons cap out at 3, which doesn't fit A-D).
"""
import os
import httpx

WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
GRAPH_URL = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"

HEADERS = {
    "Authorization": f"Bearer {WHATSAPP_TOKEN}",
    "Content-Type": "application/json",
}


async def send_text(to: str, body: str) -> None:
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body},
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        await client.post(GRAPH_URL, headers=HEADERS, json=payload)


async def send_list(to: str, header: str, body: str, button_text: str, rows: list[dict]) -> None:
    """
    rows: list of {"id": "...", "title": "...", "description": "..."} (max 10)
    Used for both the subject menu and question answer options.
    """
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "text", "text": header[:60]},
            "body": {"text": body[:1024]},
            "action": {
                "button": button_text[:20],
                "sections": [{"title": "Options", "rows": rows[:10]}],
            },
        },
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        await client.post(GRAPH_URL, headers=HEADERS, json=payload)


def extract_incoming_message(payload: dict) -> dict | None:
    """
    Parses Meta's webhook payload down to {"from": phone, "type": "text"|"interactive", "text": str, "list_id": str|None}
    Returns None if this isn't a user message (e.g. a status update webhook).
    """
    try:
        entry = payload["entry"][0]
        change = entry["changes"][0]["value"]
        if "messages" not in change:
            return None
        msg = change["messages"][0]
        from_number = msg["from"]

        if msg["type"] == "text":
            return {"from": from_number, "type": "text", "text": msg["text"]["body"], "list_id": None}

        if msg["type"] == "interactive":
            interactive = msg["interactive"]
            if interactive["type"] == "list_reply":
                return {
                    "from": from_number,
                    "type": "interactive",
                    "text": interactive["list_reply"]["title"],
                    "list_id": interactive["list_reply"]["id"],
                }
        return None
    except (KeyError, IndexError):
        return None
