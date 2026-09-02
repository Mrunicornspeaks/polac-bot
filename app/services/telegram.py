"""
Thin wrapper around Telegram's Bot API, matching the interface of
app/services/whatsapp.py (send_text, send_list, extract_incoming_message)
so app/bot.py's conversation logic works completely unchanged - only the
import line in bot.py switches between the two.

WhatsApp "list" messages don't exist on Telegram, so send_list is
implemented as a text message with an inline keyboard - one button per
row, stacked vertically, in the same order as the WhatsApp rows.
"""
import os
import httpx

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


async def send_text(to: str, body: str) -> None:
    payload = {"chat_id": to, "text": body}
    async with httpx.AsyncClient(timeout=15.0) as client:
        await client.post(f"{API_URL}/sendMessage", json=payload)


async def send_list(to: str, header: str, body: str, button_text: str, rows: list[dict]) -> None:
    """
    rows: list of {"id": "...", "title": "...", "description": "..."} — same shape
    whatsapp.send_list expects. Descriptions are folded into the button label
    since Telegram buttons don't support a separate description line.
    """
    text = f"*{header}*\n\n{body}"
    keyboard = []
    for row in rows[:10]:
        label = row["title"]
        if row.get("description"):
            label = f"{label} — {row['description']}"
        keyboard.append([{"text": label[:64], "callback_data": row["id"][:64]}])

    payload = {
        "chat_id": to,
        "text": text,
        "parse_mode": "Markdown",
        "reply_markup": {"inline_keyboard": keyboard},
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        await client.post(f"{API_URL}/sendMessage", json=payload)


async def answer_callback(callback_query_id: str) -> None:
    """Clears the loading spinner Telegram shows on a tapped button. Fire-and-forget."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        await client.post(
            f"{API_URL}/answerCallbackQuery",
            json={"callback_query_id": callback_query_id},
        )


def extract_incoming_message(payload: dict) -> dict | None:
    """
    Parses a Telegram update down to the same shape whatsapp.py produces:
    {"from": chat_id, "type": "text"|"interactive", "text": str, "list_id": str|None}
    Returns None for update types we don't act on.
    """
    if "message" in payload and "text" in payload["message"]:
        msg = payload["message"]
        chat_id = str(msg["chat"]["id"])
        return {"from": chat_id, "type": "text", "text": msg["text"], "list_id": None}

    if "callback_query" in payload:
        cq = payload["callback_query"]
        chat_id = str(cq["message"]["chat"]["id"])
        return {
            "from": chat_id,
            "type": "interactive",
            "text": cq["data"],
            "list_id": cq["data"],
            "_callback_query_id": cq["id"],  # consumed by the webhook route to ack the tap
        }

    return None
