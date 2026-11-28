"""Signed Meta WhatsApp webhook endpoints for inbound messages and statuses."""
from __future__ import annotations

import hashlib
import hmac
import json
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse

from state.manager import state_manager

app = FastAPI(title="WealthOS WhatsApp Webhook", docs_url=None, redoc_url=None)


def valid_signature(raw: bytes, signature: str, app_secret: str) -> bool:
    if not signature.startswith("sha256=") or not app_secret:
        return False
    expected = "sha256=" + hmac.new(app_secret.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@app.get("/webhooks/whatsapp")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode", "")
    token = request.query_params.get("hub.verify_token", "")
    challenge = request.query_params.get("hub.challenge", "")
    verify_token = os.getenv("WHATSAPP_WEBHOOK_VERIFY_TOKEN", "")
    if mode != "subscribe" or not verify_token or not hmac.compare_digest(token, verify_token):
        raise HTTPException(status_code=403, detail="Webhook verification failed")
    return PlainTextResponse(challenge)


@app.post("/webhooks/whatsapp")
async def receive_webhook(request: Request):
    raw = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    app_secret = os.getenv("WHATSAPP_APP_SECRET", "")
    if not valid_signature(raw, signature, app_secret):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON") from exc
    if payload.get("object") != "whatsapp_business_account":
        raise HTTPException(status_code=400, detail="Unexpected webhook object")
    saved = state_manager.save_whatsapp_webhook(payload)
    # Acknowledge promptly; webhook processing stores inbound activity but sends no reply.
    return {"received": True, "events_saved": saved}
