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
```

---

## Troubleshooting

**ModuleNotFoundError** — make sure you've activated the virtual env:
```bash
source .venv/bin/activate
```

**Mono 401 error** — your `MONO_SECRET_KEY` is wrong or using test key against live endpoint. Double-check the key in your Mono dashboard.

**Mono 404 on account** — your `MONO_ACCOUNT_ID` is incorrect. Re-run the Connect widget to get a fresh account code and exchange it for an ID.

**Paystack 401 error** — ensure the key starts with `sk_live_` (live) or `sk_test_` (test), not `pk_` (that's the public key).
