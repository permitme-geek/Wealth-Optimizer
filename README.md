# WealthOS

WealthOS tracks verified financial progress and creates practical sales and income actions. Run commands from this directory with the project's virtual environment:

```bash
source .venv/bin/activate
python cli.py setup
python cli.py wealth
python cli.py daily-report
```

## Changes made today — 28 November 2026

- Reworked `setup` to show a starting wealth assessment and initial recommendation before collecting the user's details. Existing balances and profile values are used as defaults; setup asks for a compact aggregate investment balance rather than requiring separate manual entry for every asset class.
- Added a daily revenue KPI equal to **3.5% of the monthly revenue goal**. For a ₦1,000,000 monthly target, the daily KPI is ₦35,000. The dashboard and daily brief show verified credited revenue, monthly progress, and the remaining daily target gap. This is a tracking goal, not an earnings promise.
- Added daily balance carry-forward. Each brief saves a dated net-worth and bank-cash snapshot and compares it with the previous report.
- Added a personalized daily brief with goal progress, verified receipts, outstanding receivables, current rating, and highest-priority sales actions.
- Added a macOS spoken reminder at the scheduled brief time. It announces verified revenue versus the daily target, achievement percentage, the next action, and any account-sync failure. Set `VOICE_REMINDERS=false` in `.env` to disable speech.
- The app coordinates these steps with a deterministic wealth-intelligence rules engine. It does not currently use a generative AI model or independently execute sales actions.
- Added optional email delivery through user-configured SMTP, alongside the terminal report log.
- Added tests for starting baselines, daily carry-forward, receipt validation, transfer exclusion, and the 3.5% KPI.
- Added a signed WhatsApp Cloud API webhook that verifies Meta subscriptions and event signatures, stores inbound replies, and exposes them through `whatsapp-inbox`.
- Added WhatsApp connection checks and commands to submit three opt-in marketing template drafts to Meta and inspect their review status. Submission is not approval; Meta must approve each template before proactive use.

## What to expect tomorrow

The macOS LaunchAgent is installed and loaded. It runs daily at 8:00 AM, syncs Paystack, records the day's balance and net worth, compares them with the previous snapshot, calculates successful inflows against the daily and monthly targets, and speaks the recommended next action.

The brief will append to `reports/daily.log`; if SMTP details are configured, it will also email the same brief. The scheduler is currently loaded and waiting for its calendar trigger. The Mac must be awake and the user session available at the scheduled time for a LaunchAgent to run. Check `reports/scheduler-error.log` if the run fails, and `reports/scheduler.log` for scheduler output.

## Useful commands

```bash
python cli.py setup            # review current standing and configure user profile/KPIs
python cli.py wealth           # wealth dashboard and best immediate actions
python cli.py daily-report     # run and record the daily brief now
python cli.py daily-schedule   # install or reload the 8:00 AM LaunchAgent
python cli.py sales-add        # add a prospect or sales opportunity
python cli.py sales-list       # inspect the sales pipeline
python cli.py lead-add         # add a traveller enquiry
python cli.py lead-inbox       # review leads and draft status
python cli.py lead-draft 1     # prepare an unsent personalized draft
python cli.py lead-approve 1   # approve a draft for manual sending
python cli.py lead-followups   # review due follow-ups
python cli.py whatsapp-setup   # save WhatsApp Cloud API credentials securely
python cli.py whatsapp-test    # validate the business phone-number connection
python cli.py whatsapp-webhook # start inbound webhook locally on port 8765
python cli.py whatsapp-inbox   # review captured inbound replies
python cli.py whatsapp-template-submit trip_enquiry # submit a draft for Meta review
python cli.py whatsapp-templates # inspect template review status
python cli.py receipt-candidates # list Paystack inflows eligible for receipt matching
python cli.py goal-add         # add a measurable wealth goal
python -m unittest discover -s tests -v
```

Daily app-related inflows count successful Paystack business payments. Sales receipts must match an imported Paystack transaction reference and amount. Paystack success records do not independently establish later bank settlement.

Re-enter or replace the Paystack key with `python cli.py paystack-setup`; input is hidden and the key is not printed. Mono authentication and connector files have been removed.

Configure and verify daily email delivery with `python cli.py email-setup` and `python cli.py email-test`. SMTP credentials are collected through hidden prompts and saved locally in `.env`.

See [SETUP.md](SETUP.md#whatsapp-business-connection) for WhatsApp credentials, webhook hosting, and template review steps. A public HTTPS host and Meta business credentials are required before Meta can deliver real webhook events. Free-form replies are permitted only inside the 24-hour customer-service window after a customer messages; proactive contact requires an approved template and valid opt-in.
