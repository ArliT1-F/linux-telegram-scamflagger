# Telegram Scam & Promo Analyzer (Listener + Vercel API)

A privacy-first message risk analyzer with two deployment modes:

1. **Telegram listener (local runtime)** for evidence capture from your own account.
2. **Vercel-hosted web app + API** for on-demand message scoring in the browser.

This project focuses on **documentation and risk scoring**, not harassment or enforcement automation.

---

## What Was Improved

- Added a **hostable Vercel app** (`api/index.py`) with:
  - `GET /` interactive analyzer UI
  - `GET /api/health` health check
  - `POST /api/analyze` JSON scoring API
- Refactored scoring into a shared `detector.py` module used by both the listener and API.
- Improved listener reliability:
  - Uses environment variables for secrets (`TELEGRAM_API_ID`, `TELEGRAM_API_HASH`)
  - Replaces unsafe shell deletes with Python `shutil.rmtree`
  - Fixes `/flag` background scan to correctly iterate async messages
  - More robust evidence folder naming to avoid collisions
- Added deployment files:
  - `vercel.json`
  - `requirements.txt`
  - `.gitignore`

---

## Architecture

```text
detector.py          # Shared scoring logic + confidence labels
telegram_listener.py # Local Telethon listener + evidence capture
api/index.py         # Flask app for Vercel hosting (UI + API)
```

---

## Detection Signals (Rule-Based)

Each message is scored transparently using:

- suspicious keywords (adult, payment, redirect/funnel)
- phone number detection
- external link detection
- long-message heuristic
- combo bonuses (e.g., payment + redirect)

Confidence mapping:

| Score | Meaning |
|------:|---------|
| 0–29  | LOW |
| 30–59 | MEDIUM |
| 60–100| HIGH |

Default save threshold: **30**

---

## Deploy on Vercel

### 1) Install Vercel CLI (optional local flow)

```bash
npm i -g vercel
```

### 2) Deploy

From repo root:

```bash
vercel
```

For production:

```bash
vercel --prod
```

Vercel will use `vercel.json` and route all traffic to the Flask app in `api/index.py`.

---

## API Usage

### Health

```bash
curl https://<your-deployment>/api/health
```

### Analyze

```bash
curl -X POST https://<your-deployment>/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"message":"Hey add me on WhatsApp +1 555 555 5555"}'
```

Example response:

```json
{
  "score": 80,
  "confidence": "HIGH",
  "reasons": ["whatsapp (+20)", "phone number (+40)", "adult + redirect combo (+20)"],
  "threshold": 30,
  "should_save": true
}
```

---

## Local Listener Setup (Telegram)

### Requirements

- Python 3.10+
- Telegram account

Install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Set credentials:

```bash
export TELEGRAM_API_ID="12345678"
export TELEGRAM_API_HASH="your_api_hash"
```

Run listener:

```bash
python3 telegram_listener.py
```

Optional environment variables:

- `SAVE_THRESHOLD` (default `30`)
- `RETENTION_DAYS` (default `30`)
- `FLAG_SCAN_LIMIT` (default `500`)
- `EVIDENCE_DIR`, `WHITELIST_FILE`, `BLACKLIST_FILE`, `PAUSE_FLAG`

---

## Evidence Output

Flagged content is saved under:

```yaml
evidence/YYYY-MM-DD/<sender_id>_<HH-MM-SS_microseconds>/
├── message.txt
└── meta.json
```

`meta.json` contains platform, sender id, timestamp, score, confidence, and reasons.

---

## Privacy Notes

- No database by default
- No full-chat archival
- Only suspicious messages are persisted
- Listener logic runs locally on your machine

---

## Disclaimer

Use this project responsibly and in compliance with local law and platform terms.  
It is intended for personal safety workflows and evidence organization.