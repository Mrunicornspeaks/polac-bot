import os
from fastapi import APIRouter, Request, Response
from app.services.whatsapp import extract_incoming_message
from app.bot import handle_incoming_message

router = APIRouter()

VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN")


@router.get("/webhook")
async def verify_webhook(request: Request):
    """
    Meta calls this once when you set up the webhook in the App dashboard,
    to confirm you control this endpoint.
    """
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return Response(content=challenge, media_type="text/plain")
    return Response(content="Verification failed", status_code=403)


@router.post("/webhook")
async def receive_webhook(request: Request):
    """
    Meta POSTs every incoming message (and delivery/status updates) here.
    We only act on actual user messages; everything else is ignored.
    """
    payload = await request.json()
    msg = extract_incoming_message(payload)
    if msg:
        await handle_incoming_message(msg)
    return Response(status_code=200)
