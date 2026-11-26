# WealthOS — Setup Guide

## Getting Your Credentials

You need **three values** before live data works. Here's exactly where to find each one.

---

## 1. Mono API — Wema Bank Connection

### Step 1.1 — Get your Mono Secret Key

1. Go to [https://app.mono.co](https://app.mono.co) and sign in
2. Navigate to **Settings → API Keys**
3. Copy the **Secret Key** (starts with `test_sk_` for sandbox or `live_sk_` for production)
4. Paste it into `.env` as `MONO_SECRET_KEY`

> **Use the test key first** — it connects to sandbox Wema Bank data so you can verify the integration before using live credentials.

---

### Step 1.2 — Link Your Wema Bank Account (Get Account ID)

Mono requires you to go through their Connect widget to link your actual bank. Here's how to get your `account_id`:

**Option A — Mono Dashboard (easiest)**
1. In your Mono dashboard, go to **Connect → Test Connect**
2. Select **Wema Bank** from the bank list
3. Enter your Wema Bank internet banking credentials
4. After successful connection, copy the **Account ID** shown in the response
5. Paste it into `.env` as `MONO_ACCOUNT_ID`

**Option B — Mono Connect via temporary HTML page**

Save this as `connect.html`, open it in your browser, complete the widget, and copy the `account_id` from the alert:

```html
<!DOCTYPE html>
<html>
<body>
  <button onclick="connectMono()">Connect Wema Bank</button>
  <script src="https://connect.mono.co/connect.js"></script>
  <script>
    function connectMono() {
      const connect = new Connect({
        key: "YOUR_MONO_PUBLIC_KEY",  // from Mono dashboard → Settings → Public Key
        onSuccess: function(data) {
          alert("Account ID: " + data.code);
          // Exchange this code for account_id via API
        }
      });
      connect.setup();
      connect.open();
    }
  </script>
</body>
</html>
```

> **Note:** The `code` returned by the widget must be exchanged for an `account_id` via:
> `POST https://api.withmono.com/v2/accounts/auth` with `{ "code": "your_code" }`
> The response contains the `account_id` — store this in `.env`.

---

## 2. Paystack Secret Key

1. Go to [https://dashboard.paystack.com](https://dashboard.paystack.com)
2. Navigate to **Settings → API Keys & Webhooks**
3. Copy the **Secret Key** (starts with `sk_live_` for production or `sk_test_` for sandbox)
4. Paste into `.env` as `PAYSTACK_SECRET_KEY`

---

## 3. Your Financial Values (for .env)

Update these values in `.env` with your actual numbers:

| Variable | What to enter |
|---|---|
| `HYSA_YIELD_RATE` | Your actual Wema HYSA rate as decimal (e.g., `0.105` for 10.5%) |
| `MONTHLY_INCOME_ESTIMATE` | Your average monthly net income in ₦ |
| `MONTHLY_EXPENSE_ESTIMATE` | Your average monthly expenses in ₦ |
| `EQUITIES_VALUE` | Current market value of your NSE stocks in ₦ |
| `BONDS_VALUE` | Current value of FGN bonds in ₦ |
| `MONEY_MARKET_VALUE` | Current value of money market funds / T-bills in ₦ |
| `OTHER_ASSETS_VALUE` | Other investments (Cowrywise, Bamboo, etc.) in ₦ |
| `WEALTH_GOAL` | Your target net worth in ₦ (e.g., `50000000` for ₦50M) |

---

## Running WealthOS

```bash
# One-time setup
chmod +x setup.sh && ./setup.sh

# First run: personal details, account auth, KPIs, starting balances and goals
python cli.py setup

# Every session — activate the virtual environment first
source .venv/bin/activate

# First run — enter your numbers interactively
python cli.py seed

# Run full report (works immediately with seeded data, no API keys needed)
python cli.py report

# Once API keys are in .env — pull live bank data
python cli.py sync

# Daily workflow
python cli.py sync && python cli.py report

# Quick commands
python cli.py status       # portfolio snapshot
python cli.py optimize     # MVO + Kelly + recommendations
python cli.py project      # Monte Carlo 60-month projection
python cli.py next-naira   # where does the next ₦1 go?
python cli.py wealth       # realised income, sales trail and next actions
python cli.py daily-report # sync, compare today's opening balance and issue actions
python cli.py daily-schedule # install the local 8:00 AM scheduled report
python cli.py wealth-profile # add skills, offers, resources and available time
python cli.py sales-list   # view sales pipeline
python cli.py sales-history 1 # inspect opportunity 1 activity trail
python cli.py sales-adjust 1 # record cost or refund
python cli.py receipt-candidates # list synced business credits available to verify
```

`setup` stores optional Mono/Paystack credentials and SMTP credentials in `.env` with owner-only file permissions. The first saved balances become the starting baseline. You can add more goals with `goal-add`, and edit the monetisation profile with `wealth-profile`. The daily brief carries forward the last report's closing net worth, records today's balance snapshot, and shows the change, current wealth progress, goals and highest-priority actions. On macOS, `daily-schedule` installs and loads a LaunchAgent for 8:00 AM system-local time. It appends terminal output to `reports/daily.log`; when SMTP is configured, it emails the same brief. Set up SMTP details during onboarding to enable delivery to both destinations. Set the Mac's timezone to the desired report timezone before installing the schedule.

On macOS, voice reminders are enabled by default (`VOICE_REMINDERS=true`). The daily brief speaks verified revenue versus the daily KPI, achievement percentage and the next action; it also calls out account sync failures. Set `VOICE_REMINDERS=false` in `.env` to turn off speech. WealthOS uses a deterministic rules engine to coordinate recorded financial data, goals and recommendations; it does not use a generative AI model or autonomously perform outreach.

The default revenue KPI is **3.5% of the monthly revenue target per day**. For example, a ₦1,000,000 monthly target yields a ₦35,000 daily target. The dashboard and daily brief show actual synced account credits against that KPI, the shortfall, monthly progress, and a next action. The KPI is a tracking target, not a promise of earnings.

## Wealth and Sales Tracking

The first saved financial snapshot is retained as the starting baseline. Verified income is read from synced Mono bank-account salary, business-income, other-income and interest credits; transfers and Paystack-only payment confirmations are excluded until the funds appear in the bank. The wealth rating is based on net realised sales earnings, completed sales, closed-sale conversion and profitability. Portfolio projections, quotes, accepted offers, invoices, pending payments and prospecting activity are displayed separately and do not count as realised earnings.

Use `python cli.py wealth-profile` to record skills, products or services, target customers, pricing constraints, resources, time and channels available for monetisation. Create a lead with `python cli.py sales-add`, then log contacts, offer changes, objections, negotiations and follow-ups with `python cli.py sales-log <id>`. After syncing Mono, use `python cli.py receipt-candidates` to find an unlinked credited transaction. `python cli.py sales-receipt <id>` records it only when its transaction ID, NGN amount and business-income category match the designated bank ledger. A Paystack success by itself is not treated as money received. Add a cost or refund with `python cli.py sales-adjust <id>`; net realised sales earnings subtract these entries. Use `python cli.py sales-history <id>` to review the dated trail.

The local SQLite sales trail retains the origin, marketing activity, contact, offer, quote, channel, stage changes, follow-up dates, payment references, receipts and adjustments. Check IDs and categories carefully before recording a receipt; only synced Mono business-income credits from the designated bank account are accepted as proof of sales payment.

---

## Troubleshooting

**ModuleNotFoundError** — make sure you've activated the virtual env:
```bash
source .venv/bin/activate
```

**Mono 401 error** — your `MONO_SECRET_KEY` is wrong or using test key against live endpoint. Double-check the key in your Mono dashboard.

**Mono 404 on account** — your `MONO_ACCOUNT_ID` is incorrect. Re-run the Connect widget to get a fresh account code and exchange it for an ID.

**Paystack 401 error** — ensure the key starts with `sk_live_` (live) or `sk_test_` (test), not `pk_` (that's the public key).
