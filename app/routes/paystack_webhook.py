import hashlib
import hmac
import os
from fastapi import APIRouter, Request, Response
from app.services.payment import verify_transaction
from app.services.users import update_user
from app.services.whatsapp import send_text

router = APIRouter()

PAYSTACK_SECRET_KEY = os.environ.get("PAYSTACK_SECRET_KEY", "")


@router.post("/paystack/webhook")
async def paystack_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("x-paystack-signature", "")

    # Verify this webhook genuinely came from Paystack, not a spoofed request
    expected = hmac.new(PAYSTACK_SECRET_KEY.encode(), body, hashlib.sha512).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return Response(status_code=401)

    payload = await request.json()
    if payload.get("event") == "charge.success":
        reference = payload["data"]["reference"]
        verified = await verify_transaction(reference)
        if verified:
            phone_number = verified.get("metadata", {}).get("phone_number")
            if phone_number:
                update_user(phone_number, {"has_paid": True})
                await send_text(
                    phone_number,
                    "✅ Payment received! You now have unlimited access. "
                    "Type *next* to keep practicing.",
                )

    return Response(status_code=200)
