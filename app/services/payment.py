"""
Paystack integration. Two things this bot needs:
  1. Generate a payment link to send in chat
  2. Verify a transaction when Paystack's webhook confirms payment
"""
import os
import httpx

PAYSTACK_SECRET_KEY = os.environ.get("PAYSTACK_SECRET_KEY")
ACCESS_PRICE_NAIRA = int(os.environ.get("ACCESS_PRICE_NAIRA", "2000"))
PAYSTACK_BASE = "https://api.paystack.co"

HEADERS = {
    "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
    "Content-Type": "application/json",
}


async def generate_payment_link(phone_number: str) -> str | None:
    """
    Paystack requires an email; since we only have a phone number, we use
    a synthetic placeholder email tied to the number. This is fine because
    we never rely on Paystack's email for anything - only the reference.
    """
    payload = {
        "email": f"{phone_number}@polacprep.ng",
        "amount": ACCESS_PRICE_NAIRA * 100,  # Paystack expects kobo
        "reference": f"polac_{phone_number}_{os.urandom(4).hex()}",
        "metadata": {"phone_number": phone_number},
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(f"{PAYSTACK_BASE}/transaction/initialize", headers=HEADERS, json=payload)
        if resp.status_code == 200:
            data = resp.json()
            return data["data"]["authorization_url"]
    return None


async def verify_transaction(reference: str) -> dict | None:
    """Called from the Paystack webhook route to confirm a payment really succeeded."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(f"{PAYSTACK_BASE}/transaction/verify/{reference}", headers=HEADERS)
        if resp.status_code == 200:
            data = resp.json()["data"]
            if data["status"] == "success":
                return data
    return None
