import asyncio
import json
import os
import shutil
import threading
from datetime import datetime, timedelta
from pathlib import Path

from telethon import TelegramClient, events

from detector import DEFAULT_CONFIG, analyze_message, confidence_label

# ==========================
# CONFIG
# ==========================
API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")

SESSION_NAME = os.getenv("SESSION_NAME", "user_session")
EVIDENCE_DIR = Path(os.getenv("EVIDENCE_DIR", "evidence"))
WHITELIST_FILE = Path(os.getenv("WHITELIST_FILE", "whitelist.txt"))
BLACKLIST_FILE = Path(os.getenv("BLACKLIST_FILE", "blacklist.txt"))
PAUSE_FLAG = Path(os.getenv("PAUSE_FLAG", "pause.flag"))

RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "30"))
SAVE_THRESHOLD = int(os.getenv("SAVE_THRESHOLD", str(DEFAULT_CONFIG.save_threshold)))
FLAG_SCAN_LIMIT = int(os.getenv("FLAG_SCAN_LIMIT", "500"))
if SAVE_THRESHOLD != DEFAULT_CONFIG.save_threshold:
    print(
        f"[!] SAVE_THRESHOLD={SAVE_THRESHOLD} differs from detector "
        f"default {DEFAULT_CONFIG.save_threshold}.",
    )

# ==========================
# SETUP
# ==========================
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

if API_ID <= 0 or not API_HASH:
    raise RuntimeError(
        "Missing TELEGRAM_API_ID/TELEGRAM_API_HASH environment variables. "
        "Set both before running telegram_listener.py."
    )

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)


def load_ids(path: Path) -> set[int]:
    if not path.exists():
        return set()
    with path.open(encoding="utf-8") as handle:
        return {int(line.strip()) for line in handle if line.strip().isdigit()}


whitelist = load_ids(WHITELIST_FILE)
blacklist = load_ids(BLACKLIST_FILE)


# ==========================
# EVIDENCE HANDLING
# ==========================
def save_evidence(sender_id: int, message: str, score: int, reasons: list[str]) -> None:
    now = datetime.now()
    base = EVIDENCE_DIR / now.strftime("%Y-%m-%d")
    base.mkdir(parents=True, exist_ok=True)

    folder = base / f"{sender_id}_{now.strftime('%H-%M-%S_%f')}"
    folder.mkdir()

    (folder / "message.txt").write_text(message, encoding="utf-8")
    (folder / "meta.json").write_text(
        json.dumps(
            {
                "platform": "Telegram",
                "sender_id": sender_id,
                "timestamp": now.isoformat(),
                "score": score,
                "confidence": confidence_label(score),
                "reasons": reasons,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def cleanup_old_evidence() -> None:
    cutoff_date = (datetime.now() - timedelta(days=RETENTION_DAYS)).date()
    for candidate in EVIDENCE_DIR.iterdir():
        if not candidate.is_dir():
            continue
        try:
            folder_date = datetime.strptime(candidate.name, "%Y-%m-%d").date()
        except ValueError:
            continue
        if folder_date < cutoff_date:
            shutil.rmtree(candidate, ignore_errors=True)


def cleanup_worker() -> None:
    while True:
        cleanup_old_evidence()
        threading.Event().wait(86400)


threading.Thread(target=cleanup_worker, daemon=True).start()


# ==========================
# MESSAGE LISTENER
# ==========================
@client.on(events.NewMessage(incoming=True))
async def handler(event):
    if PAUSE_FLAG.exists():
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
        daemon=True,
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
    await event.respond("Flagging conversation in background...")

    async def worker():
        scanned = 0
        saved = 0
        async for message in client.iter_messages(chat_id, limit=FLAG_SCAN_LIMIT):
            text = message.raw_text or ""
            if not text or message.sender_id is None:
                continue
            scanned += 1
            score, reasons = analyze_message(text)
            if score >= SAVE_THRESHOLD:
                saved += 1
                save_evidence(message.sender_id, text, score, reasons)
        await event.respond(f"Flag scan complete. Scanned {scanned} messages, saved {saved}.")

    asyncio.create_task(worker())


@client.on(events.NewMessage(pattern=r"^/skip$"))
async def skip_user(event):
    if not event.is_reply:
        await event.respond("Reply to a message to skip that user.")
        return

    message = await event.get_reply_message()
    if not message or message.sender_id is None:
        await event.respond("Could not resolve a sender from that reply.")
        return

    uid = message.sender_id
    if uid not in whitelist:
        whitelist.add(uid)
        with WHITELIST_FILE.open("a", encoding="utf-8") as handle:
            handle.write(f"{uid}\n")

    for date_folder in EVIDENCE_DIR.iterdir():
        if not date_folder.is_dir():
            continue
        for sender_folder in date_folder.iterdir():
            if sender_folder.is_dir() and sender_folder.name.startswith(f"{uid}_"):
                shutil.rmtree(sender_folder, ignore_errors=True)

    await event.respond("User whitelisted and existing evidence removed.")


# ==========================
# RUN
# ==========================
print("[+] Telegram listener running (enhanced)")
client.start()
client.run_until_disconnected()
