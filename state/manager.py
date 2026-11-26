"""
state/manager.py — Financial State Manager
Maintains a real-time snapshot of your complete financial picture.
Persists to SQLite so state survives between CLI runs.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional
import json, sqlite3, os
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)


@dataclass
class FinancialState:
    # ── Balances (₦) ──────────────────────────────────────────
    hysa_balance:          float = 0.0
    hysa_yield_rate:       float = 0.105
    equities_value:        float = 0.0
    bonds_value:           float = 0.0
    money_market_value:    float = 0.0
    other_assets_value:    float = 0.0

    # ── Cash flow (₦/month) ────────────────────────────────────
    monthly_income_avg:    float = 0.0
    monthly_expense_avg:   float = 0.0

    # ── Metadata ───────────────────────────────────────────────
    last_synced:           Optional[str] = None   # ISO timestamp
    data_source:           str = "manual"         # "paystack" | "manual"

    # ── Computed (not stored, derived on access) ───────────────
    @property
    def total_net_worth(self) -> float:
        return (self.hysa_balance + self.equities_value +
                self.bonds_value + self.money_market_value +
                self.other_assets_value)

    @property
    def monthly_surplus(self) -> float:
        return self.monthly_income_avg - self.monthly_expense_avg

    @property
    def savings_rate(self) -> float:
        if self.monthly_income_avg <= 0:
            return 0.0
        return self.monthly_surplus / self.monthly_income_avg

    @property
    def liquid_months(self) -> float:
        """How many months of expenses the HYSA covers."""
        if self.monthly_expense_avg <= 0:
            return 0.0
        return self.hysa_balance / self.monthly_expense_avg

    @property
    def hysa_weight(self) -> float:
        w = self.total_net_worth
        return self.hysa_balance / w if w > 0 else 0.0

    @property
    def allocation(self) -> dict:
        w = self.total_net_worth
        if w == 0:
            return {k: 0.0 for k in ["HYSA","Equities","Bonds","MoneyMarket","Other"]}
        return {
            "HYSA":        self.hysa_balance       / w,
            "Equities":    self.equities_value      / w,
            "Bonds":       self.bonds_value          / w,
            "MoneyMarket": self.money_market_value  / w,
            "Other":       self.other_assets_value  / w,
        }

    def real_hysa_return(self, inflation: float = 0.30) -> float:
        return (1 + self.hysa_yield_rate) / (1 + inflation) - 1


class StateManager:
    """Persists financial state to SQLite. Thread-safe for single-user CLI use."""

    DB_PATH = Path("wealthos.db")

    def __init__(self):
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS financial_state (
                    id       INTEGER PRIMARY KEY,
                    state    TEXT NOT NULL,
                    updated  TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id          TEXT PRIMARY KEY,
                    amount      REAL,
                    txn_type    TEXT,
                    narration   TEXT,
                    date        TEXT,
                    source      TEXT,
                    category    TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS wealth_baseline (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    net_worth REAL NOT NULL,
                    monthly_income REAL NOT NULL,
                    monthly_expenses REAL NOT NULL,
                    recorded_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_balances (
                    report_date TEXT PRIMARY KEY,
                    net_worth REAL NOT NULL,
                    hysa REAL NOT NULL,
                    equities REAL NOT NULL,
                    bonds REAL NOT NULL,
                    money_market REAL NOT NULL,
                    other_assets REAL NOT NULL,
                    recorded_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_goals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    goal TEXT NOT NULL,
                    target_amount REAL NOT NULL DEFAULT 0,
                    target_date TEXT NOT NULL DEFAULT '',
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS opportunities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'manual',
                    marketing_activity TEXT NOT NULL DEFAULT '',
                    customer TEXT NOT NULL,
                    contact TEXT NOT NULL DEFAULT '',
                    offer TEXT NOT NULL,
                    quoted_amount REAL NOT NULL DEFAULT 0,
                    currency TEXT NOT NULL DEFAULT 'NGN',
                    channel TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'prospect',
                    payment_status TEXT NOT NULL DEFAULT 'unpaid',
                    accepted_amount REAL NOT NULL DEFAULT 0,
                    received_amount REAL NOT NULL DEFAULT 0,
                    payment_date TEXT NOT NULL DEFAULT '',
                    transaction_reference TEXT NOT NULL DEFAULT '',
                    costs REAL NOT NULL DEFAULT 0,
                    refund_amount REAL NOT NULL DEFAULT 0,
                    next_follow_up TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sales_activities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    opportunity_id INTEGER NOT NULL,
                    occurred_at TEXT NOT NULL,
                    activity_type TEXT NOT NULL,
                    notes TEXT NOT NULL DEFAULT '',
                    amount REAL NOT NULL DEFAULT 0,
                    FOREIGN KEY(opportunity_id) REFERENCES opportunities(id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS wealth_profile (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    skills TEXT NOT NULL DEFAULT '',
                    offers TEXT NOT NULL DEFAULT '',
                    display_name TEXT NOT NULL DEFAULT '',
                    target_customers TEXT NOT NULL DEFAULT '',
                    pricing_notes TEXT NOT NULL DEFAULT '',
                    resources TEXT NOT NULL DEFAULT '',
                    available_hours REAL NOT NULL DEFAULT 0,
                    preferred_channels TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL
                )
            """)
            profile_columns = {row[1] for row in conn.execute("PRAGMA table_info(wealth_profile)")}
            for column in ("target_customers", "pricing_notes", "display_name"):
                if column not in profile_columns:
                    conn.execute(f"ALTER TABLE wealth_profile ADD COLUMN {column} TEXT NOT NULL DEFAULT ''")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS verified_receipts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    opportunity_id INTEGER NOT NULL,
                    transaction_reference TEXT NOT NULL UNIQUE,
                    amount REAL NOT NULL CHECK(amount >= 0),
                    payment_date TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    FOREIGN KEY(opportunity_id) REFERENCES opportunities(id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sales_adjustments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    opportunity_id INTEGER NOT NULL,
                    adjustment_type TEXT NOT NULL CHECK(adjustment_type IN ('cost','refund')),
                    amount REAL NOT NULL CHECK(amount >= 0),
                    occurred_at TEXT NOT NULL,
                    reference TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY(opportunity_id) REFERENCES opportunities(id)
                )
            """)
            conn.commit()

    # ── Read / Write ──────────────────────────────────────────
    def get(self) -> FinancialState:
        with sqlite3.connect(self.DB_PATH) as conn:
            row = conn.execute(
                "SELECT state FROM financial_state ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if row:
            data = json.loads(row[0])
            # Drop fields from previous Mono-based state snapshots during migration.
            data.pop("mono_account_id", None)
            if data.get("data_source") == "mono":
                data["data_source"] = "manual"
            return FinancialState(**data)
        return FinancialState()

    def save(self, state: FinancialState) -> None:
        payload = {k: v for k, v in asdict(state).items()}
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.DB_PATH) as conn:
            conn.execute(
                "INSERT INTO financial_state (state, updated) VALUES (?, ?)",
                (json.dumps(payload), now)
            )
            # keep only last 500 snapshots
            conn.execute(
                "DELETE FROM financial_state WHERE id NOT IN "
                "(SELECT id FROM financial_state ORDER BY id DESC LIMIT 500)"
            )
            conn.execute(
                "INSERT OR IGNORE INTO wealth_baseline VALUES (1, ?, ?, ?, ?)",
                (state.total_net_worth, state.monthly_income_avg,
                 state.monthly_expense_avg, now),
            )
            conn.commit()

    def save_transactions(self, txns: list[dict]) -> int:
        """Upserts transactions. Returns count of new records inserted."""
        new_count = 0
        with sqlite3.connect(self.DB_PATH) as conn:
            for t in txns:
                try:
                    conn.execute(
                        "INSERT INTO transactions VALUES (?,?,?,?,?,?,?)",
                        (t["id"], t["amount"], t["type"],
                         t.get("narration",""), t["date"],
                         t.get("source","paystack"), t.get("category",""))
                    )
                    new_count += 1
                except sqlite3.IntegrityError:
                    pass  # already exists
            conn.commit()
        return new_count

    def get_transactions(self, limit: int = 200) -> list[dict]:
        with sqlite3.connect(self.DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM transactions ORDER BY date DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_unlinked_business_credits(self, limit: int = 100) -> list[dict]:
        with sqlite3.connect(self.DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""SELECT t.* FROM transactions t
                LEFT JOIN verified_receipts r ON r.transaction_reference=t.id
                WHERE t.txn_type='credit' AND t.category='business_income'
                  AND t.source='paystack' AND r.id IS NULL
                ORDER BY t.date DESC LIMIT ?""", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def ensure_baseline(self, state: FinancialState | None = None) -> dict:
        """Record the first known financial snapshot as a comparison baseline."""
        state = state or self.get()
        with sqlite3.connect(self.DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM wealth_baseline WHERE id=1").fetchone()
            if row is None and any((state.total_net_worth, state.monthly_income_avg,
                                    state.monthly_expense_avg)):
                conn.execute(
                    "INSERT INTO wealth_baseline VALUES (1, ?, ?, ?, ?)",
                    (state.total_net_worth, state.monthly_income_avg,
                     state.monthly_expense_avg, datetime.now(timezone.utc).isoformat()),
                )
                row = conn.execute("SELECT * FROM wealth_baseline WHERE id=1").fetchone()
        if row is None:
            return {"net_worth": state.total_net_worth,
                    "monthly_income": state.monthly_income_avg,
                    "monthly_expenses": state.monthly_expense_avg,
                    "recorded_at": "baseline pending"}
        return dict(row)

    def add_opportunity(self, *, customer: str, offer: str, quoted_amount: float,
                        source: str = "manual", channel: str = "", contact: str = "",
                        marketing_activity: str = "", next_follow_up: str = "") -> int:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.DB_PATH) as conn:
            cur = conn.execute("""INSERT INTO opportunities
                (created_at, source, marketing_activity, customer, contact, offer,
                 quoted_amount, channel, next_follow_up, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (now, source, marketing_activity, customer, contact, offer,
                 max(float(quoted_amount), 0), channel, next_follow_up, now))
            oid = int(cur.lastrowid)
            conn.execute("INSERT INTO sales_activities (opportunity_id, occurred_at, activity_type, notes) VALUES (?, ?, ?, ?)",
                         (oid, now, "created", f"Opportunity created via {source}"))
            conn.commit()
        return oid

    def list_opportunities(self, limit: int = 500) -> list[dict]:
        with sqlite3.connect(self.DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute(
                "SELECT * FROM opportunities ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()]

    def update_opportunity(self, opportunity_id: int, *, activity_type: str,
                           notes: str = "", status: str | None = None,
                           amount: float | None = None, payment_status: str | None = None,
                           transaction_reference: str = "", costs: float | None = None,
                           refund_amount: float | None = None, next_follow_up: str | None = None,
                           payment_date: str = "") -> None:
        allowed = {"prospect", "lead", "opportunity", "proposed", "accepted", "invoiced",
                   "won", "lost", "refunded"}
        statuses = {"unpaid", "pending", "partial", "paid", "refunded"}
        if status is not None and status not in allowed:
            raise ValueError(f"Invalid stage: {status}")
        if status == "won":
            raise ValueError("A sale is marked won when its synced business receipt is recorded")
        if payment_status is not None and payment_status not in statuses:
            raise ValueError(f"Invalid payment status: {payment_status}")
        if payment_status == "paid" and not transaction_reference.strip():
            raise ValueError("A transaction reference is required to record a verified receipt")
        now = datetime.now(timezone.utc).isoformat()
        fields, vals = ["updated_at=?"], [now]
        for column, value in (("status", status), ("accepted_amount", amount),
                              ("payment_status", payment_status),
                              ("transaction_reference", transaction_reference or None),
                              ("costs", costs), ("refund_amount", refund_amount),
                              ("next_follow_up", next_follow_up)):
            if value is not None:
                fields.append(f"{column}=?"); vals.append(value)
        if payment_status == "paid" and amount is not None:
            fields.extend(["received_amount=?", "payment_date=?"])
            vals.extend([amount, payment_date or datetime.now(timezone.utc).date().isoformat()])
        vals.append(opportunity_id)
        with sqlite3.connect(self.DB_PATH) as conn:
            cur = conn.execute(f"UPDATE opportunities SET {', '.join(fields)} WHERE id=?", vals)
            if cur.rowcount == 0:
                raise ValueError(f"Opportunity #{opportunity_id} not found")
            conn.execute("""INSERT INTO sales_activities
                (opportunity_id, occurred_at, activity_type, notes, amount)
                VALUES (?, ?, ?, ?, ?)""",
                (opportunity_id, now, activity_type, notes, amount or 0))
            conn.commit()

    def opportunity_history(self, opportunity_id: int) -> list[dict]:
        with sqlite3.connect(self.DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute(
                "SELECT * FROM sales_activities WHERE opportunity_id=? ORDER BY occurred_at",
                (opportunity_id,)).fetchall()]

    def record_receipt(self, opportunity_id: int, amount: float, reference: str,
                       payment_date: str = "", costs: float = 0) -> None:
        """Append a receipt only with an account transaction reference; duplicate refs are rejected."""
        if amount <= 0 or not reference.strip():
            raise ValueError("A positive receipt amount and transaction reference are required")
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.DB_PATH) as conn:
            cur = conn.execute("SELECT received_amount, costs FROM opportunities WHERE id=?", (opportunity_id,)).fetchone()
            if cur is None:
                raise ValueError(f"Opportunity #{opportunity_id} not found")
            txn = conn.execute("SELECT amount, txn_type, source, category, date FROM transactions WHERE id=?",
                               (reference.strip(),)).fetchone()
            if txn is None:
                raise ValueError("Transaction reference was not found in synced account/payment transactions")
            if txn[1] != "credit" or txn[3] != "business_income" or txn[2] != "paystack":
                raise ValueError("Only successful synced Paystack business-income payments can verify a sales receipt")
            if abs(float(txn[0]) - amount) > 0.01:
                raise ValueError(f"Receipt amount must match the synced transaction ({txn[0]:,.2f} NGN)")
            paid_date = txn[4]
            if payment_date and payment_date != paid_date:
                raise ValueError(f"Payment date must match the synced account transaction ({paid_date})")
            try:
                conn.execute("INSERT INTO verified_receipts (opportunity_id, transaction_reference, amount, payment_date, recorded_at) VALUES (?, ?, ?, ?, ?)",
                             (opportunity_id, reference.strip(), amount, paid_date, now))
            except sqlite3.IntegrityError as exc:
                raise ValueError("That transaction reference has already been recorded") from exc
            conn.execute("""UPDATE opportunities SET received_amount=?, payment_status='paid',
                status='won', payment_date=?, transaction_reference=?, costs=?, updated_at=? WHERE id=?""",
                (cur[0] + amount, paid_date, reference.strip(), cur[1] + max(costs, 0), now, opportunity_id))
            if costs > 0:
                conn.execute("INSERT INTO sales_adjustments (opportunity_id, adjustment_type, amount, occurred_at, reference, notes) VALUES (?, 'cost', ?, ?, ?, ?)",
                             (opportunity_id, costs, now, reference.strip(), "Costs associated with receipt"))
            conn.execute("INSERT INTO sales_activities (opportunity_id, occurred_at, activity_type, notes, amount) VALUES (?, ?, 'receipt_verified', ?, ?)",
                         (opportunity_id, now, f"Receipt against account transaction reference {reference.strip()}", amount))
            conn.commit()

    def record_adjustment(self, opportunity_id: int, adjustment_type: str, amount: float,
                          notes: str = "", reference: str = "") -> None:
        if adjustment_type not in {"cost", "refund"} or amount <= 0:
            raise ValueError("Adjustment must be a positive cost or refund")
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.DB_PATH) as conn:
            row = conn.execute("SELECT costs, refund_amount FROM opportunities WHERE id=?", (opportunity_id,)).fetchone()
            if row is None:
                raise ValueError(f"Opportunity #{opportunity_id} not found")
            column = "costs" if adjustment_type == "cost" else "refund_amount"
            conn.execute(f"UPDATE opportunities SET {column}=?, updated_at=? WHERE id=?",
                         (row[0 if adjustment_type == "cost" else 1] + amount, now, opportunity_id))
            conn.execute("INSERT INTO sales_adjustments (opportunity_id, adjustment_type, amount, occurred_at, reference, notes) VALUES (?, ?, ?, ?, ?, ?)",
                         (opportunity_id, adjustment_type, amount, now, reference, notes))
            conn.execute("INSERT INTO sales_activities (opportunity_id, occurred_at, activity_type, notes, amount) VALUES (?, ?, ?, ?, ?)",
                         (opportunity_id, now, adjustment_type, notes, amount))
            conn.commit()

    def save_profile(self, *, skills: str, offers: str, display_name: str = "", target_customers: str,
                     pricing_notes: str, resources: str, available_hours: float,
                     preferred_channels: str) -> None:
        with sqlite3.connect(self.DB_PATH) as conn:
            conn.execute("""INSERT INTO wealth_profile
                (id, skills, offers, display_name, target_customers, pricing_notes, resources,
                 available_hours, preferred_channels, updated_at)
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET skills=excluded.skills, offers=excluded.offers,
                display_name=excluded.display_name,
                target_customers=excluded.target_customers, pricing_notes=excluded.pricing_notes,
                resources=excluded.resources, available_hours=excluded.available_hours,
                preferred_channels=excluded.preferred_channels, updated_at=excluded.updated_at""",
                (skills, offers, display_name, target_customers, pricing_notes, resources,
                 max(0, available_hours), preferred_channels,
                 datetime.now(timezone.utc).isoformat()))

    def get_profile(self) -> dict:
        with sqlite3.connect(self.DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM wealth_profile WHERE id=1").fetchone()
        return dict(row) if row else {"skills": "", "offers": "", "display_name": "", "target_customers": "",
                                      "pricing_notes": "", "resources": "",
                                      "available_hours": 0, "preferred_channels": ""}

    def record_daily_balance(self, state: FinancialState, report_date: str) -> dict:
        values = (report_date, state.total_net_worth, state.hysa_balance,
                  state.equities_value, state.bonds_value, state.money_market_value,
                  state.other_assets_value, datetime.now(timezone.utc).isoformat())
        with sqlite3.connect(self.DB_PATH) as conn:
            conn.execute("INSERT INTO daily_balances VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                         "ON CONFLICT(report_date) DO UPDATE SET net_worth=excluded.net_worth, "
                         "hysa=excluded.hysa, equities=excluded.equities, bonds=excluded.bonds, "
                         "money_market=excluded.money_market, other_assets=excluded.other_assets, "
                         "recorded_at=excluded.recorded_at", values)
            current = conn.execute("SELECT * FROM daily_balances WHERE report_date=?", (report_date,)).fetchone()
            previous = conn.execute("SELECT * FROM daily_balances WHERE report_date < ? ORDER BY report_date DESC LIMIT 1", (report_date,)).fetchone()
        return {"current": current, "previous": previous}

    def add_goal(self, goal: str, target_amount: float = 0, target_date: str = "") -> int:
        with sqlite3.connect(self.DB_PATH) as conn:
            cur = conn.execute("INSERT INTO user_goals (goal,target_amount,target_date,created_at) VALUES (?,?,?,?)",
                               (goal, max(target_amount, 0), target_date, datetime.now(timezone.utc).isoformat()))
            return int(cur.lastrowid)

    def get_goals(self) -> list[dict]:
        with sqlite3.connect(self.DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute("SELECT * FROM user_goals WHERE active=1 ORDER BY id")]

    def wealth_metrics(self, state: FinancialState | None = None) -> dict[str, Any]:
        """Separate recorded receipts, pipeline, costs and profit; projections stay out."""
        state = state or self.get()
        baseline = self.ensure_baseline(state)
        opportunities = self.list_opportunities()
        timezone_name = os.getenv("WEALTHOS_TIMEZONE", "Africa/Lagos")
        today = datetime.now(ZoneInfo(timezone_name)).date()
        month_start = today.replace(day=1).isoformat()
        with sqlite3.connect(self.DB_PATH) as conn:
            verified_income = conn.execute("""SELECT amount, date FROM transactions
                WHERE txn_type='credit' AND category='business_income'
                  AND source='paystack'""").fetchall()
            sales_receipts = conn.execute("SELECT amount, payment_date FROM verified_receipts").fetchall()
        received_month = sum(amount for amount, dt in verified_income if dt >= month_start)
        received_total = sum(amount for amount, _ in verified_income)
        daily_received = sum(amount for amount, dt in verified_income if dt == today.isoformat())
        monthly_revenue_target = float(os.getenv("MONTHLY_INCOME_TARGET", "0") or 0)
        sales_received = sum(amount for amount, _ in sales_receipts)
        with sqlite3.connect(self.DB_PATH) as conn:
            refunds, costs = conn.execute("""SELECT
                COALESCE(SUM(CASE WHEN adjustment_type='refund' THEN amount ELSE 0 END), 0),
                COALESCE(SUM(CASE WHEN adjustment_type='cost' THEN amount ELSE 0 END), 0)
                FROM sales_adjustments""").fetchone()
        outstanding = sum(max(o["accepted_amount"] - o["received_amount"], 0)
                          for o in opportunities if o["status"] in {"accepted", "invoiced", "won"})
        active = [o for o in opportunities if o["status"] not in {"won", "lost", "refunded"}]
        won = [o for o in opportunities if o["status"] == "won"]
        closed = [o for o in opportunities if o["status"] in {"won", "lost"}]
        conversion = len(won) / len(closed) if closed else 0.0
        with sqlite3.connect(self.DB_PATH) as conn:
            activity_count, followup_count = conn.execute("""SELECT
                COUNT(*),
                COALESCE(SUM(CASE WHEN activity_type LIKE '%follow%' THEN 1 ELSE 0 END), 0)
                FROM sales_activities a JOIN opportunities o ON o.id=a.opportunity_id""",
                ()).fetchone()
            due_count = conn.execute("""SELECT COUNT(*) FROM opportunities WHERE next_follow_up <> ''
                AND next_follow_up <= ? AND status NOT IN ('won','lost','refunded')""",
                (today.isoformat(),)).fetchone()[0]
        metrics = {"baseline": baseline, "received_month": received_month,
                "received_total": received_total, "sales_received": sales_received,
                "daily_received": daily_received,
                "daily_revenue_target": monthly_revenue_target * 0.035,
                "monthly_revenue_target": monthly_revenue_target,
                "refunds": refunds, "costs": costs,
                "net_realised": sales_received - refunds - costs,
                "outstanding": outstanding,
                "pipeline_value": sum(o["quoted_amount"] for o in active),
                "won_count": len(won), "opportunity_count": len(opportunities),
                "activity_count": activity_count, "followup_count": followup_count,
                "followups_due": due_count,
                "conversion_rate": conversion, "opportunities": opportunities,
                "net_worth_change": state.total_net_worth - baseline["net_worth"]}
        target = max(baseline["monthly_income"], state.monthly_income_avg, 100_000)
        margin = max(metrics["net_realised"], 0) / sales_received if sales_received > 0 else 0
        metrics["rating_breakdown"] = {
            "verified_net_earnings": round(50 * min(max(metrics["net_realised"], 0) / target, 1), 1),
            "completed_sales": round(20 * min(len(won) / 5, 1), 1),
            "closed_sale_conversion": round(15 * min(conversion / 0.3, 1), 1),
            "profitability": round(15 * min(margin, 1), 1),
        }
        metrics["rating"] = round(sum(metrics["rating_breakdown"].values()))
        return metrics

    # ── Rolling average helpers ────────────────────────────────
    @staticmethod
    def rolling_ema(current: float, new_val: float, alpha: float = 0.15) -> float:
        """Exponential moving average: weights recent values more heavily."""
        return alpha * new_val + (1 - alpha) * current

    def recompute_cash_flow(self, state: FinancialState) -> FinancialState:
        """Recompute monthly income/expense averages from stored transactions."""
        txns = self.get_transactions(limit=500)
        if not txns:
            return state

        from collections import defaultdict
        monthly_income  = defaultdict(float)
        monthly_expense = defaultdict(float)

        for t in txns:
            month_key = t["date"][:7]  # "YYYY-MM"
            if t["txn_type"] == "credit":
                monthly_income[month_key]  += t["amount"]
            else:
                monthly_expense[month_key] += t["amount"]

        if monthly_income:
            state.monthly_income_avg  = sum(monthly_income.values())  / len(monthly_income)
        if monthly_expense:
            state.monthly_expense_avg = sum(monthly_expense.values()) / len(monthly_expense)

        return state


# Singleton
state_manager = StateManager()
