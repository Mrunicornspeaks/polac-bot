from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv()

from app.routes import whatsapp_webhook, telegram_webhook, paystack_webhook  # noqa: E402  (must load env first)

app = FastAPI(title="POLAC Prep Bot")

app.include_router(whatsapp_webhook.router)
app.include_router(telegram_webhook.router)
app.include_router(paystack_webhook.router)


@app.get("/")
async def health_check():
    return {"status": "ok", "service": "POLAC Prep Bot"}
