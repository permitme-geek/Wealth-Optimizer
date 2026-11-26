# WealthOS Setup

WealthOS uses Paystack successful payment transactions as its source for app-related inflows. It no longer connects through Mono. A successful Paystack payment confirms a payment through Paystack; it does not independently confirm a later bank settlement.

## Initial setup

```bash
source .venv/bin/activate
python cli.py setup
```

Setup reviews the saved financial position first, then collects the profile, balances, revenue goal, 3.5% daily revenue KPI, offers and daily-report settings. The first saved financial snapshot becomes the starting baseline.

To enter or replace your Paystack key at any time:

```bash
python cli.py paystack-setup
```

The key is entered using a hidden prompt, saved in the local `.env` file with owner-only permissions, and never printed. Then import and review the successful Paystack payment records:

```bash
python cli.py sync
python cli.py wealth
python cli.py receipt-candidates
```

## Daily reports

```bash
python cli.py daily-report
python cli.py daily-schedule
```

The macOS LaunchAgent runs at 8:00 AM system-local time. It syncs Paystack, records a dated balance snapshot, compares it with the previous snapshot, reports successful inflows against the daily and monthly revenue goals, and gives the highest-priority next actions. It writes to `reports/daily.log`, speaks a brief progress reminder, and emails the brief when SMTP has been configured during setup.

The daily revenue KPI is 3.5% of the monthly revenue goal. It is a tracking target, not a promise of earnings. Use `python cli.py wealth-profile` to adapt skills, offers, buyer segments, pricing, resources and channels. Add goals with `python cli.py goal-add`.

## Sales trail

Create and update sales opportunities with:

```bash
python cli.py sales-add
python cli.py sales-log <id>
python cli.py sales-history <id>
python cli.py sales-receipt <id>
python cli.py sales-adjust <id>
```

Sales receipts are counted only when their transaction reference and amount match an imported successful Paystack business payment. Refunds and recorded costs reduce net realised sales earnings. Quotes, invoices, receivables and unverified promises remain separate from realised income.

## Tests

```bash
python -m unittest discover -s tests -v
```
