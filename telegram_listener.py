import re
import os
import json
import threading
from datetime import datetime, timedelta
from telethon import TelegramClient, events

# ==========================
# CONFIG
# ==========================
API_ID = 12345678
API_HASH = "YOUR_API_HASH_HERE"

SESSION_NAME = "user_session"
EVIDENCE_DIR = "evidence"
WHITELIST_FILE = "whitelist.txt"
BLACKLIST_FILE = "blacklist.txt"
PAUSE_FLAG = "pause.flag"

RETENTION_DAYS = 30
SAVE_THRESHOLD = 30

# ==========================
# KEYWORDS & PHRASES
# ==========================
KEYWORDS = {
    "onlyfans": 30,
    "only fans": 30,
    "escort": 30,
    "cam girl": 25,
    "nudes": 20,
    "premium content": 25,
    "private content": 20,
    "paid": 20,
    "payment": 20,
    "pay me": 20,
    "paypal": 25,
    "cashapp": 25,
    "venmo": 25,
    "bitcoin": 30,
    "btc": 25,
    "usdt": 25,
    "whatsapp": 20,
    "telegram.me": 20,
    "t.me/": 20
}

PHONE_REGEX = re.compile(r"\+?\d[\d\s\-().]{7,}")
LINK_REGEX = re.compile(r"https?://\S+|wa\.me/\S+|t\.me/\S+")

LONG_MESSAGE_THRESHOLD = 200
LONG_MESSAGE_SCORE = 15

PHONE_SCORE = 40
LINK_SCORE = 25
COMBO_BONUS = 20

# ==========================
# SETUP
# ==========================
os.makedirs(EVIDENCE_DIR, exist_ok=True)
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

def load_ids(path):
    if not os.path.exists(path):
        return set()
    with open(path) as f:
        return set(int(x.strip()) for x in f if x.strip().isdigit())

whitelist = load_ids(WHITELIST_FILE)
blacklist = load_ids(BLACKLIST_FILE)

# ==========================
# SCORING
# ==========================
def analyze_message(text):
    score = 0
    reasons = []
    lowered = text.lower()

    payment = redirect = adult = False

    for kw, pts in KEYWORDS.items():
        if kw in lowered:
            score += pts
            reasons.append(f"{kw} (+{pts})")

            if kw in ["paypal", "cashapp", "venmo", "bitcoin", "btc", "usdt", "paid", "payment"]:
                payment = True
            if kw in ["whatsapp", "telegram", "snapchat", "instagram", "dm me", "add me on"]:
                redirect = True
            if kw in ["onlyfans", "only fans", "escort", "cam girl", "nudes", "premium content"]:
                adult = True

    if PHONE_REGEX.search(text):
        score += PHONE_SCORE
        reasons.append("phone number")
        redirect = True

    if LINK_REGEX.search(text):
        score += LINK_SCORE
        reasons.append("external link")
        redirect = True

    if len(text) > LONG_MESSAGE_THRESHOLD:
        score += LONG_MESSAGE_SCORE
        reasons.append("long message")

    if payment and redirect:
        score += COMBO_BONUS
        reasons.append("payment + redirect combo")

    if adult and redirect:
        score += COMBO_BONUS
        reasons.append("adult + redirect combo")

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
    date_dir = datetime.now().strftime("%Y-%m-%d")
    base = os.path.join(EVIDENCE_DIR, date_dir)
    os.makedirs(base, exist_ok=True)

    ts = datetime.now().strftime("%H-%M-%S")
    folder = os.path.join(base, f"{sender_id}_{ts}")
    os.makedirs(folder)

    with open(f"{folder}/message.txt", "w", encoding="utf-8") as f:
        f.write(message)

    with open(f"{folder}/meta.json", "w", encoding="utf-8") as f:
        json.dump({
            "platform": "Telegram",
            "sender_id": sender_id,
            "timestamp": datetime.now().isoformat(),
            "score": score,
            "confidence": confidence_label(score),
            "reasons": reasons
        }, f, indent=2)

# ==========================
# CLEANUP THREAD
# ==========================
def cleanup_old_evidence():
    cutoff = datetime.now() - timedelta(days=RETENTION_DAYS)
    for root, dirs, files in os.walk(EVIDENCE_DIR):
        for d in dirs:
            path = os.path.join(root, d)
            try:
                dt = datetime.strptime(d.split("_")[0], "%Y-%m-%d")
                if dt < cutoff:
                    os.system(f"rm -rf '{path}'")
            except:
                pass

def cleanup_worker():
    while True:
        cleanup_old_evidence()
        threading.Event().wait(86400)

threading.Thread(target=cleanup_worker, daemon=True).start()

# ==========================
# MESSAGE LISTENER
# ==========================
@client.on(events.NewMessage(incoming=True))
async def handler(event):
    if os.path.exists(PAUSE_FLAG):
        return

    sender = await event.get_sender()
    if not sender:
        return

    if sender.id in whitelist:
        return

    text = event.raw_text or ""
    if not text:
        return

    score, reasons = analyze_message(text)

    if score < SAVE_THRESHOLD and sender.id not in blacklist:
        return

    threading.Thread(
        target=save_evidence,
        args=(sender.id, text, score, reasons),
        daemon=True
    ).start()

# ==========================
# COMMANDS
# ==========================
@client.on(events.NewMessage(pattern=r"^/flag$"))
async def flag_chat(event):
    if not event.is_reply:
        await event.respond("Reply to a message to flag the entire chat.")
        return

    chat_id = event.chat_id
    await event.respond("Flagging conversation in background…")

    def worker():
        for msg in client.iter_messages(chat_id, limit=500):
            if not msg.raw_text:
                continue
            score, reasons = analyze_message(msg.raw_text)
            if score >= SAVE_THRESHOLD:
                save_evidence(msg.sender_id, msg.raw_text, score, reasons)

    threading.Thread(target=worker, daemon=True).start()

@client.on(events.NewMessage(pattern=r"^/skip$"))
async def skip_user(event):
    if not event.is_reply:
        await event.respond("Reply to a message to skip that user.")
        return

    msg = await event.get_reply_message()
    uid = msg.sender_id

    whitelist.add(uid)
    with open(WHITELIST_FILE, "a") as f:
        f.write(f"{uid}\n")

    def remove_evidence():
        for root, dirs, files in os.walk(EVIDENCE_DIR):
            for d in dirs:
                if d.startswith(str(uid)):
                    os.system(f"rm -rf '{os.path.join(root, d)}'")

    threading.Thread(target=remove_evidence, daemon=True).start()
    await event.respond("User whitelisted and evidence removed.")

# ==========================
# RUN
# ==========================
print("[+] Telegram listener running (enhanced)")
client.start()
client.run_until_disconnected()
