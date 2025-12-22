import re
import os
from datetime import datetime
from telethon import TelegramClient, events

# ==========================
# CONFIG
# ==========================
API_ID = 123456
API_HASH = "PASTE_API_HASH_HERE"

EVIDENCE_DIR = "evidence"

KEYWORDS = {
    "onlyfans": 30,
    "escort": 30,
    "paid": 20,
    "payment": 20,
    "whatsapp": 20,
    "telegram.me": 20,
    "t.me/": 20
}

PHONE_REGEX = re.compile(r"\+?\d[\d\s\-]{7,}")
LINK_REGEX = re.compile(r"https?://\S+")

LONG_MESSAGE_THRESHOLD = 300
LONG_MESSAGE_SCORE = 15

PHONE_SCORE = 40
LINK_SCORE = 25

# ==========================
# SETUP
# ==========================
os.makedirs(EVIDENCE_DIR, exist_ok=True)
client = TelegramClient("user_session", API_ID, API_HASH)

# ==========================
# SCORING
# ==========================
def analyze_message(text: str):
    score = 0
    reasons = []

    lowered = text.lower()

    # Keyword scoring
    for kw, pts in KEYWORDS.items():
        if kw in lowered:
            score += pts
            reasons.append(f"Keyword: {kw} (+{pts})")

    # Phone number
    if PHONE_REGEX.search(text):
        score += PHONE_SCORE
        reasons.append(f"Phone number detected (+{PHONE_SCORE})")

    # External link
    if LINK_REGEX.search(text):
        score += LINK_SCORE
        reasons.append(f"External link (+{LINK_SCORE})")

    # Long first reply
    if len(text) > LONG_MESSAGE_THRESHOLD:
        score += LONG_MESSAGE_SCORE
        reasons.append(f"Long message (+{LONG_MESSAGE_SCORE})")

    return min(score, 100), reasons

def confidence_label(score):
    if score >= 60:
        return "HIGH"
    if score >= 30:
        return "MEDIUM"
    return "LOW"

# ==========================
# EVIDENCE HANDLING
# ==========================
def save_evidence(sender_id, message, score, reasons):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = os.path.join(EVIDENCE_DIR, timestamp)
    os.makedirs(path)

    with open(f"{path}/platform.txt", "w") as f:
        f.write("Telegram")

    with open(f"{path}/sender.txt", "w") as f:
        f.write(str(sender_id))

    with open(f"{path}/message.txt", "w") as f:
        f.write(message)

    with open(f"{path}/confidence.txt", "w") as f:
        f.write(f"{score}% ({confidence_label(score)})")

    with open(f"{path}/reasons.txt", "w") as f:
        f.write("\n".join(reasons))

# ==========================
# LISTENER
# ==========================
@client.on(events.NewMessage(incoming=True))
async def handler(event):
    text = event.raw_text or ""
    if not text:
        return

    score, reasons = analyze_message(text)

    if score < 30:
        return  # discard low confidence

    sender = await event.get_sender()
    save_evidence(sender.id if sender else "unknown", text, score, reasons)

# ==========================
# RUN
# ==========================
print("[+] Telegram listener running with confidence scoring")
client.start()
client.run_until_disconnected()
