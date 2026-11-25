# WealthOS

WealthOS tracks verified financial progress and creates practical sales and income actions. Run commands from this directory with the project's virtual environment:

```bash
source .venv/bin/activate
python cli.py setup
python cli.py wealth
python cli.py daily-report
```

## Changes made today — 25 November 2026

- Reworked `setup` to show a starting wealth assessment and initial recommendation before collecting the user's details. Existing balances and profile values are used as defaults; setup asks for a compact aggregate investment balance rather than requiring separate manual entry for every asset class.
- Added a daily revenue KPI equal to **3.5% of the monthly revenue goal**. For a ₦1,000,000 monthly target, the daily KPI is ₦35,000. The dashboard and daily brief show verified credited revenue, monthly progress, and the remaining daily target gap. This is a tracking goal, not an earnings promise.
- Added daily balance carry-forward. Each brief saves a dated net-worth and bank-cash snapshot and compares it with the previous report.
- Added a personalized daily brief with goal progress, verified receipts, outstanding receivables, current rating, and highest-priority sales actions.
- Added optional email delivery through user-configured SMTP, alongside the terminal report log.
- Added tests for starting baselines, daily carry-forward, receipt validation, transfer exclusion, and the 3.5% KPI.

## What to expect tomorrow

The macOS LaunchAgent is installed and loaded. Its first scheduled run is **Thursday, 26 November 2026 at 8:00 AM Africa/Lagos time**. It will attempt configured Mono and Paystack syncs, record the day's bank cash and net worth, compare them with the **25 November 2026** snapshot, calculate verified revenue against the daily and monthly targets, and print the day's recommended actions.

The brief will append to `reports/daily.log`; if SMTP details are configured, it will also email the same brief. The scheduler is currently loaded and waiting for its calendar trigger. The Mac must be awake and the user session available at the scheduled time for a LaunchAgent to run. Check `reports/scheduler-error.log` if the run fails, and `reports/scheduler.log` for scheduler output.

## Useful commands

```bash
python cli.py setup            # review current standing and configure user profile/KPIs
python cli.py wealth           # wealth dashboard and best immediate actions
python cli.py daily-report     # run and record the daily brief now
python cli.py daily-schedule   # install or reload the 8:00 AM LaunchAgent
python cli.py sales-add        # add a prospect or sales opportunity
python cli.py sales-list       # inspect the sales pipeline
python cli.py receipt-candidates # list synced bank credits eligible for receipt matching
python cli.py goal-add         # add a measurable wealth goal
python -m unittest discover -s tests -v
```

Daily income counts only supported credits found in synced Mono account transactions; transfers and Paystack-only payment confirmations are not treated as credited income. Sales receipts must match a synced bank transaction reference and amount.
