import os
from dotenv import load_dotenv
import httpx

load_dotenv()

token = os.environ["WHATSAPP_TOKEN"]
phone_id = os.environ["WHATSAPP_PHONE_NUMBER_ID"]

url = f"https://graph.facebook.com/v21.0/{phone_id}"
headers = {"Authorization": f"Bearer {token}"}

response = httpx.get(url, headers=headers)

print("Status code:", response.status_code)
print("Response:", response.json())
