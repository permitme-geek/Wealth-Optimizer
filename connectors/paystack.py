"""
connectors/paystack.py — Paystack income connector
Pulls successful payment receipts to track business income.

Paystack API docs: https://paystack.com/docs/api
"""
from __future__ import annotations
import httpx
from datetime import datetime, timezone, date, timedelta
from config import settings


PAYSTACK_BASE = "https://api.paystack.co"

HEADERS = {
    "Authorization": f"Bearer {settings.paystack_secret_key}",
    "Content-Type": "application/json",
}


class PaystackConnector:

    # ── Transactions (payments received) ──────────────────────
    def get_transactions(
        self,
        days_back: int = 180,
        status:    str = "success",
    ) -> list[dict]:
        """
        Fetches successful payment transactions (income you received).
        Handles pagination automatically.
        """
        from_date = (date.today() - timedelta(days=days_back)).isoformat()
        url   = f"{PAYSTACK_BASE}/transaction"
        txns  = []
        page  = 1

        while True:
            params = {
                "status":   status,
                "from":     from_date,
                "perPage":  100,
                "page":     page,
            }
            with httpx.Client(timeout=20) as client:
                r = client.get(url, headers=HEADERS, params=params)
                r.raise_for_status()
                body = r.json()

            items = body.get("data", [])
            meta  = body.get("meta", {})

            for item in items:
                txns.append(self._normalise(item))

            # Paystack meta.next indicates more pages
            if not meta.get("next") or len(items) == 0:
                break
            page += 1

        return txns

    def _normalise(self, raw: dict) -> dict:
        """Normalise Paystack transaction to WealthOS internal format."""
        # Paystack amounts are in kobo
        amount_naira = raw.get("amount", 0) / 100

        paid_at = raw.get("paid_at") or raw.get("createdAt", "")
        date_str = paid_at[:10] if paid_at else ""

        customer = raw.get("customer", {})
        meta     = raw.get("metadata") or {}

        return {
            "id":        str(raw.get("id", "")),
            "amount":    amount_naira,
            "type":      "credit",
            "narration": (
                meta.get("description")
                or raw.get("message", "")
                or f"Paystack: {customer.get('email','')}"
            )[:100],
            "date":      date_str,
            "source":    "paystack",
            "category":  "business_income",
        }

    # ── Transfers (money sent out) ─────────────────────────────
    def get_transfers(self, days_back: int = 180) -> list[dict]:
        from_date = (date.today() - timedelta(days=days_back)).isoformat()
        url   = f"{PAYSTACK_BASE}/transfer"
        txns  = []
        page  = 1

        while True:
            params = {"from": from_date, "perPage": 100, "page": page}
            with httpx.Client(timeout=20) as client:
                r = client.get(url, headers=HEADERS, params=params)
                r.raise_for_status()
                body = r.json()

            items = body.get("data", [])
            for item in items:
                if item.get("status") == "success":
                    txns.append({
                        "id":        str(item.get("id","")),
                        "amount":    item.get("amount", 0) / 100,
                        "type":      "debit",
                        "narration": item.get("reason", "Paystack transfer"),
                        "date":      (item.get("createdAt",""))[:10],
                        "source":    "paystack",
                        "category":  "transfer_out",
                    })

            if len(items) < 100:
                break
            page += 1

        return txns


def sync_paystack(verbose: bool = True) -> dict:
    """Main sync function. Call from CLI."""
    from state.manager import state_manager

    if not settings.paystack_configured:
        return {
            "success": False,
            "error": "Paystack not configured. Add PAYSTACK_SECRET_KEY to .env"
        }

    connector = PaystackConnector()

    receipts  = connector.get_transactions(days_back=180)
    transfers = connector.get_transfers(days_back=180)
    all_txns  = receipts + transfers

    new_count = state_manager.save_transactions(all_txns)

    # Recompute monthly income using new Paystack data
    state = state_manager.get()
    state = state_manager.recompute_cash_flow(state)
    state.last_synced = datetime.now(timezone.utc).isoformat()
    state_manager.save(state)

    total_income = sum(t["amount"] for t in receipts)

    return {
        "success":       True,
        "receipts":      len(receipts),
        "transfers":     len(transfers),
        "new_txns":      new_count,
        "total_income":  total_income,
        "monthly_income_avg": state.monthly_income_avg,
    }
