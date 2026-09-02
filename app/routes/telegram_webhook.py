from fastapi import APIRouter, Request, Response
from app.services.telegram import extract_incoming_message, answer_callback
from app.bot import handle_incoming_message

router = APIRouter()


@router.post("/telegram/webhook")
async def receive_webhook(request: Request):
    """
    Telegram POSTs every update here (messages and button taps).
    Unlike Meta, there's no separate verification handshake - you register
    this URL once via the setWebhook API call (see deployment notes).
    """
    payload = await request.json()
    msg = extract_incoming_message(payload)
    if msg:
        if msg.get("_callback_query_id"):
            await answer_callback(msg["_callback_query_id"])
        await handle_incoming_message(msg)
    return Response(status_code=200)
