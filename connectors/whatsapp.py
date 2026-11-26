"""Minimal WhatsApp Business Cloud API connection check and text sender."""
from __future__ import annotations

import httpx
from config import settings


class WhatsAppCloudAPI:
    def __init__(self):
        if not settings.whatsapp_configured:
            raise ValueError("WhatsApp is not configured; run `python cli.py whatsapp-setup`")
        self.base = f"https://graph.facebook.com/{settings.whatsapp_api_version}"
        self.headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}"}

    def get_phone_number(self) -> dict:
        response = httpx.get(
            f"{self.base}/{settings.whatsapp_phone_number_id}",
            headers=self.headers,
            params={"fields": "display_phone_number,verified_name,quality_rating,platform_type"},
            timeout=20,
        )
        response.raise_for_status()
        return response.json()

    def send_text(self, recipient: str, message: str) -> dict:
        """Send text only. Caller must enforce opt-in, draft approval and open service window."""
        response = httpx.post(
            f"{self.base}/{settings.whatsapp_phone_number_id}/messages",
            headers={**self.headers, "Content-Type": "application/json"},
            json={"messaging_product": "whatsapp", "recipient_type": "individual",
                  "to": recipient, "type": "text", "text": {"preview_url": False, "body": message}},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
