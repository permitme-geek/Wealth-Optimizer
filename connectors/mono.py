"""
connectors/mono.py — Mono API connector
Pulls your Wema Bank HYSA balance and transaction history.

Mono API docs: https://docs.mono.co/reference
"""
from __future__ import annotations
import httpx
from datetime import datetime, timezone
from typing import Optional
from config import settings


MONO_BASE = "https://api.withmono.com/v2"

HEADERS = {
    "mono-sec-key": settings.mono_secret_key,
    "Content-Type": "application/json",
    "Accept": "application/json",
}


class MonoConnector:

    def __init__(self, account_id: str = ""):
        self.account_id = account_id or settings.mono_account_id

    # ── Account & Balance ─────────────────────────────────────
    def get_account(self) -> dict:
        """
        Returns account details including current balance.
        Balance from Mono is in KOBO — we convert to Naira (÷100).
        """
        url = f"{MONO_BASE}/accounts/{self.account_id}"
        with httpx.Client(timeout=15) as client:
            r = client.get(url, headers=HEADERS)
            if r.status_code != 200:
                print(f"DEBUG: Mono API Error {r.status_code}")
                print(f"DEBUG: Response Body: {r.text}")
            r.raise_for_status()
            data = r.json()

        account = data.get("data", {})
        return {
            "account_id":     account.get("_id", ""),
            "institution":    account.get("institution", {}).get("name", "Unknown"),
            "account_number": account.get("accountNumber", ""),
            "account_type":   account.get("type", ""),
            "currency":       account.get("currency", "NGN"),
            "balance":        account.get("balance", 0) / 100,  # kobo → naira
            "name":           account.get("name", ""),
        }

    # ── Transaction History ────────────────────────────────────
    def get_transactions(
        self,
        start_date: Optional[str] = None,   # "YYYY-MM-DD"
        end_date:   Optional[str] = None,
        limit:      int = 500,
    ) -> list[dict]:
        """
        Fetches full transaction history and normalises to internal format.
        Handles Mono pagination automatically.
        """
        url   = f"{MONO_BASE}/accounts/{self.account_id}/transactions"
        txns  = []
        page  = 1

        while True:
            params: dict = {"paginate": "true", "limit": 100, "page": page}
            if start_date: params["start"] = start_date
            if end_date:   params["end"]   = end_date

            with httpx.Client(timeout=20) as client:
                r = client.get(url, headers=HEADERS, params=params)
                r.raise_for_status()
                body = r.json()

            data  = body.get("data", {})
            items = data.get("data", [])
            meta  = data.get("paging", {})

            for item in items:
                txns.append(self._normalise(item))

            # Stop if no more pages
            if not meta.get("next") or len(items) == 0 or len(txns) >= limit:
                break
            page += 1

        return txns[:limit]

    def _normalise(self, raw: dict) -> dict:
        """Converts a Mono transaction to WealthOS internal format."""
        # Mono amounts are in kobo
        amount_naira = abs(raw.get("amount", 0)) / 100

        return {
            "id":        raw.get("_id", ""),
            "amount":    amount_naira,
            "type":      raw.get("type", "debit").lower(),   # "credit" | "debit"
            "narration": raw.get("narration", ""),
            "date":      raw.get("date", "")[:10],           # "YYYY-MM-DD"
            "source":    "mono",
            "category":  self._categorise(raw.get("narration", ""),
                                          raw.get("type", "debit")),
        }

    @staticmethod
    def _categorise(narration: str, txn_type: str) -> str:
        """Simple rule-based transaction categoriser for Nigerian bank narrations."""
        n = narration.upper()
        if txn_type.lower() == "credit":
            if any(k in n for k in ["SALARY", "PAYROLL", "PAY "]):  return "salary"
            if any(k in n for k in ["TRANSFER FROM", "TRF FROM"]):  return "transfer_in"
            if any(k in n for k in ["INTEREST", "YIELD", "INT "]):  return "interest"
            if any(k in n for k in ["PAYSTACK", "FLUTTERWAVE"]):    return "business_income"
            return "income_other"
        else:
            if any(k in n for k in ["RENT", "LEASE", "HOUSING"]):  return "housing"
            if any(k in n for k in ["AIRTIME", "DATA", "MTN",
                                     "AIRTEL", "GLO", "ETISALAT"]): return "telecoms"
            if any(k in n for k in ["UBER", "BOLT", "TAXIFY",
                                     "TRANSPORT", "FUEL"]):          return "transport"
            if any(k in n for k in ["FOOD", "RESTAURANT", "CAFE",
                                     "SHOPRITE", "MARKET"]):         return "food"
            if any(k in n for k in ["TRANSFER TO", "TRF TO"]):      return "transfer_out"
            if any(k in n for k in ["INVESTMENT", "COWRYWISE",
                                     "BAMBOO", "RISEVEST"]):         return "investment"
            return "expense_other"


def sync_mono(verbose: bool = True) -> dict:
    """
    Main sync function. Call from CLI.
    Returns dict with updated balance and new transaction count.
    """
    from state.manager import state_manager

    if not settings.mono_configured:
        return {
            "success": False,
            "error": "Mono not configured. Add MONO_SECRET_KEY and MONO_ACCOUNT_ID to .env"
        }

    connector = MonoConnector()

    # 1. Pull account balance
    account = connector.get_account()
    balance = account["balance"]

    # 2. Pull transactions (last 6 months)
    from datetime import timedelta, date
    start = (date.today() - timedelta(days=180)).isoformat()
    transactions = connector.get_transactions(start_date=start)

    # 3. Update state
    state = state_manager.get()
    state.hysa_balance   = balance
    state.data_source    = "mono"
    state.last_synced    = datetime.now(timezone.utc).isoformat()
    state.mono_account_id = connector.account_id

    # 4. Recompute averages from transactions
    new_count = state_manager.save_transactions(transactions)
    state = state_manager.recompute_cash_flow(state)
    state_manager.save(state)

    return {
        "success":       True,
        "institution":   account["institution"],
        "balance":       balance,
        "account_type":  account["account_type"],
        "new_txns":      new_count,
        "total_txns":    len(transactions),
        "monthly_income":  state.monthly_income_avg,
        "monthly_expense": state.monthly_expense_avg,
    }
