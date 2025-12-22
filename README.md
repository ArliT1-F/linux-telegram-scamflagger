# Telegram Scam & Promo Evidence Listener

A **privacy-first Telegram listener** that runs locally on Linux and **automatically documents suspicious messages** (scams, promotions, escort ads, off-platform funnels) so they can be **reported with proper evidence** — without screenshots, bots replying, or mass surveillance.

This tool **does not punish or interact with anyone**.  
All enforcement is left to Telegram, Tinder, or the relevant platform.

---

## ✨ Key Goals

- Detect scam / promo patterns early
- Avoid storing innocent conversations
- Reduce manual screenshots and phone storage usage
- Provide **clear, explainable evidence** for reports
- Respect user privacy at all times

---

## 🚦 What This Tool Does

- Runs continuously on your **Linux Mint (or any Linux) laptop**
- Listens to **your own Telegram account** (not a bot account)
- Analyzes incoming messages **in memory only**
- Assigns a **confidence score (0–100)** based on scam signals
- Saves **only flagged messages** as evidence
- Leaves all clean messages untouched and discarded

---

## ❌ What This Tool Does NOT Do

- ❌ No auto-replies
- ❌ No mass reporting
- ❌ No conversation logging
- ❌ No scraping or crawling
- ❌ No WhatsApp or Tinder automation
- ❌ No public lists or shaming

This is a **documentation tool**, not a harassment or enforcement system.

---

## 🧠 Detection Signals (v1)

Each message is scored using transparent rules:

- Phone number detection
- External links
- Keywords (OnlyFans, escort, payment, WhatsApp, Telegram redirects)
- Unusually long messages (spam-style walls of text)

Each signal adds points, producing a **confidence score**:

| Score | Meaning |
|------|--------|
| 0–29 | Low (ignored) |
| 30–59 | Medium |
| 60–100 | High |

Only **medium and high confidence** messages are saved.

---

## 📁 Evidence Output Structure

When a message is flagged, a folder is created:
```yaml
evidence/YYYY-MM-DD_HH-MM-SS/
├── platform.txt
├── sender.txt
├── message.txt
├── confidence.txt
└── reasons.txt
```
This folder can be zipped and attached directly to a report

---

## 🔐 Privacy Design
Privacy is enforced technically, not by policy:

- No databases
- No chat history storage
- No full conversations saved
- Only flagged messages are written to disk
- All analysis is local and offline
- Innocent messages are discarded immediately

---

## 🛠 Requirements
- Linux (tested on Linux Mint)
- Python 3.9+
- Telegram account

Python dependencies:
```bash
pip install telethon
```
---

## 🔑 Telegram API Setup (One-Time)
**1.** Go to https://my.telegram.org

**2.** Log in with your phone number

**3.** Open API development tools

**4.** Copy:
- api_id
- api_hash

These authenticate your own Telegram account (similar to Telegram Desktop).

---

## ▶️ Running the Listener
```bash
python3 telegram_listener.py
```
On first run:
- Telegram will ask for a login code
- Enter it once
- A local session file is created

After that, the listener can run countinuously.

---

## ⚖️ Legal & Ethical Notes
- Telegram MTProto user sessions are officially supported
- This tool only observes messages you already recieve
- No ToS circumvention, impersonation, or automation
- Reporting decisions remain fully manual

If you are unsure about legality in your jurisdiction, **DO NOT** use the tool.

---

## 🧭 Roadmap (Optional Enhancements)
- First-message detection
- Hash-only scam pattern detection
- Encrypted evidence folders
- One-click ZIP report export
- System tray indicator
- Systemd service (run on boot)

---

## 📌 Disclaimer
This project is provided for **personal use** and **self-protection**.
The author is not responsible for misuse or ToS violations caused by modifications.

---

## ❤️ Philosophy

        Don't spy.
        Don't bait.
        Don't harass.
        Just document and report.

---

If anyone wants me to add something new... this is what I have in mind:
- Add a **threat model** section
- Add **installation as a systemd service**

Ps: These are the features that I'm currently willing to add next to the project.