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

## WhatsApp Business connection

WealthOS connects through Meta's WhatsApp Cloud API. In the Meta App Dashboard, create an app with the WhatsApp use case, connect the WhatsApp Business account, and obtain the business phone-number ID and WABA ID. Generate a permanent system-user access token with `whatsapp_business_messaging` and `whatsapp_business_management` permissions. Meta also provides a temporary test number and token during initial setup; use a permanent token for an ongoing connection. Then run:

```bash
python cli.py whatsapp-setup
python cli.py whatsapp-test
```

The access token and app secret are entered hidden and saved in `.env` with owner-only permissions. The setup command also creates a webhook verification token; save the displayed value for the Meta dashboard. The test command only reads the configured business phone-number details; it does not send a customer message.

### Receive replies through the webhook

The receiver is implemented at `/webhooks/whatsapp`. It answers Meta's GET subscription challenge and verifies POST event signatures using the Meta app secret before saving inbound messages. Start it locally with:

```bash
python cli.py whatsapp-webhook
```

This listens on `127.0.0.1:8765`. Meta cannot reach a loopback address: deploy this app behind a stable public HTTPS host/reverse proxy and forward the route `/webhooks/whatsapp` to port `8765`. Keep the webhook secret in the host's secret store (or its protected `.env`), and expose only HTTPS. In Meta App Dashboard → WhatsApp → Configuration, set the callback URL to `https://YOUR_HOST/webhooks/whatsapp`, enter the verification token printed by `whatsapp-setup`, verify, and subscribe to the `messages` webhook field. Then send a test message to the connected WhatsApp Business number and inspect it with:

```bash
python cli.py whatsapp-inbox
```

### Submit proactive message templates

Three marketing template drafts are included. Submit a draft after confirming the wording and that the intended recipients opted in:

```bash
python cli.py whatsapp-template-submit trip_enquiry
python cli.py whatsapp-template-submit quote_followup
python cli.py whatsapp-template-submit repeat_booking
python cli.py whatsapp-templates
```

Meta reviews templates on the connected WABA. A submission can remain pending or be rejected; check its returned status and review it in Meta before use. This integration does not send proactive messages. Free-form messages are available only during the 24-hour customer-service window after the customer messages you; outside that window, use an approved template. Honor opt-outs and only contact people who gave permission.

Enable email notifications without repeating the full onboarding flow:

```bash
python cli.py email-setup
python cli.py email-test
```

Use an SMTP app password rather than your normal email password. Gmail commonly uses `smtp.gmail.com:587`; Outlook commonly uses `smtp-mail.outlook.com:587`. Port 587 uses STARTTLS and port 465 uses SSL. The password is hidden during entry and stored in `.env` with owner-only permissions.

## Daily reports

```bash
python cli.py daily-report
python cli.py daily-schedule
```

The macOS LaunchAgent runs at 8:00 AM system-local time. It syncs Paystack, records a dated balance snapshot, compares it with the previous snapshot, reports successful inflows against the daily and monthly revenue goals, and gives the highest-priority next actions. It writes to `reports/daily.log`, speaks a brief progress reminder, and emails the brief when SMTP has been configured during setup.

The daily revenue KPI is 3.5% of the monthly revenue goal. It is a tracking target, not a promise of earnings. Use `python cli.py wealth-profile` to adapt skills, offers, buyer segments, pricing, resources and channels. Add goals with `python cli.py goal-add`.

## Sales trail

Use `lead-add` to capture a traveller enquiry, contact permission and trip requirements. `lead-draft <id>` makes an unsent personalized template; `lead-approve <id>` requires your explicit approval; `lead-sent <id>` records that you sent it manually and queues a follow-up date. Use `lead-inbox` and `lead-followups` to triage the inbox. Drafting is blocked unless permission to contact is recorded. WealthOS does not send messages automatically in this first build.

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
