from fastapi import APIRouter, Request, Response, BackgroundTasks
from app.services.telegram import extract_incoming_message, answer_callback
from app.bot import handle_incoming_message
 
router = APIRouter()
 
 
@router.post("/telegram/webhook")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Telegram POSTs every update here (messages and button taps).
    We ack with 200 immediately and hand the actual work (which can be
    slow when it hits Groq for an explanation) to a background task -
    otherwise a slow Groq call keeps Telegram's request open, and a user
    tapping a button again while waiting queues up duplicate work that
    all lands at once when things finally clear.
    Unlike Meta, there's no separate verification handshake - you register
    this URL once via the setWebhook API call (see deployment notes).
    """
    payload = await request.json()
    msg = extract_incoming_message(payload)
    if msg:
        if msg.get("_callback_query_id"):
            background_tasks.add_task(answer_callback, msg["_callback_query_id"])
        background_tasks.add_task(handle_incoming_message, msg)
    return Response(status_code=200)
 
