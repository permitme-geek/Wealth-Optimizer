import tempfile
import unittest
import os
from pathlib import Path

from state.manager import FinancialState, StateManager


class WealthProgressTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.previous_path = StateManager.DB_PATH
        StateManager.DB_PATH = Path(self.tempdir.name) / "test.sqlite3"
        self.manager = StateManager()

    def tearDown(self):
        StateManager.DB_PATH = self.previous_path
        self.tempdir.cleanup()

    def test_first_saved_state_becomes_baseline(self):
        state = FinancialState(hysa_balance=125_000, monthly_income_avg=80_000)
        self.manager.save(state)
        metrics = self.manager.wealth_metrics(state)
        self.assertEqual(metrics["baseline"]["net_worth"], 125_000)
        self.assertEqual(metrics["rating"], 0)

    def test_empty_state_does_not_lock_zero_baseline(self):
        self.manager.wealth_metrics(FinancialState())
        state = FinancialState(hysa_balance=200_000)
        self.manager.save(state)
        self.assertEqual(self.manager.wealth_metrics(state)["baseline"]["net_worth"], 200_000)

    def test_daily_balance_carries_forward_and_compares_to_previous_day(self):
        self.manager.record_daily_balance(FinancialState(hysa_balance=100), "2026-01-01")
        result = self.manager.record_daily_balance(FinancialState(hysa_balance=125), "2026-01-02")
        self.assertEqual(result["previous"][1], 100)
        self.assertEqual(result["current"][1], 125)

    def test_receipt_requires_matching_synced_business_credit(self):
        opportunity = self.manager.add_opportunity(customer="Buyer", offer="Service", quoted_amount=500)
        self.manager.save_transactions([{"id": "txn-1", "amount": 500, "type": "credit",
            "date": "2026-01-01", "source": "mono", "category": "business_income"}])
        self.manager.record_receipt(opportunity, 500, "txn-1")
        self.assertEqual(self.manager.wealth_metrics()["sales_received"], 500)
        with self.assertRaises(ValueError):
            self.manager.record_receipt(opportunity, 500, "txn-1")

    def test_transfer_is_not_verified_income_or_sales(self):
        self.manager.save_transactions([{"id": "txn-transfer", "amount": 900, "type": "credit",
            "date": "2026-01-01", "source": "mono", "category": "transfer_in"}])
        metrics = self.manager.wealth_metrics()
        self.assertEqual(metrics["received_total"], 0)
        self.assertEqual(metrics["sales_received"], 0)

    def test_daily_revenue_kpi_is_3_5_percent_of_monthly_goal(self):
        previous = os.environ.get("MONTHLY_INCOME_TARGET")
        os.environ["MONTHLY_INCOME_TARGET"] = "1000000"
        try:
            metrics = self.manager.wealth_metrics(FinancialState())
            self.assertEqual(metrics["daily_revenue_target"], 35_000)
        finally:
            if previous is None:
                os.environ.pop("MONTHLY_INCOME_TARGET", None)
            else:
                os.environ["MONTHLY_INCOME_TARGET"] = previous


if __name__ == "__main__":
    unittest.main()
