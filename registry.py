"""Scam registry storage and monthly publication helpers."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path


_WRITE_LOCK = threading.Lock()


@dataclass(frozen=True)
class RegistryConfig:
    # This file receives every new detected entry immediately.
    live_file: Path = Path("scam_registry_live.txt")
    download_dir: Path = Path("registry_downloads")
    download_meta_file: Path = Path("registry_download_meta.json")
    cooldown_days: int = 30
    downloadable_filename: str = "scam_registry_download.txt"


def classify_scam_type(reasons: list[str]) -> str:
    """Infer a coarse scam type from matched detection reasons."""
    lowered = " | ".join(reasons).lower()

    adult = any(token in lowered for token in ("onlyfans", "escort", "cam girl", "nudes", "premium content"))
    payment = any(token in lowered for token in ("paypal", "cashapp", "venmo", "bitcoin", "btc", "usdt", "payment", "pay me", "paid"))
    redirect = any(token in lowered for token in ("whatsapp", "telegram.me", "t.me/", "phone number", "external link"))

    if adult and payment and redirect:
        return "adult-payment-funnel"
    if adult and redirect:
        return "adult-redirect"
    if payment and redirect:
        return "payment-redirect"
    if adult:
        return "adult-promo"
    if payment:
        return "payment-request"
    if redirect:
        return "redirect-funnel"
    return "suspicious-pattern"


def _sanitize(value: str) -> str:
    return value.replace("\n", " ").replace("\r", " ").replace("|", "/").strip()


def _header_line() -> str:
    return "timestamp | name | identifier | scam_type | score | confidence\n"


def _ensure_live_file(config: RegistryConfig) -> None:
    config.live_file.parent.mkdir(parents=True, exist_ok=True)
    if config.live_file.exists():
        return
    config.live_file.write_text(_header_line(), encoding="utf-8")


def _published_path(config: RegistryConfig) -> Path:
    return config.download_dir / config.downloadable_filename


def _ensure_downloadable_file(config: RegistryConfig) -> Path:
    config.download_dir.mkdir(parents=True, exist_ok=True)
    target = _published_path(config)
    if not target.exists():
        target.write_text(_header_line(), encoding="utf-8")
    return target


def append_registry_entry(
    config: RegistryConfig,
    *,
    name: str,
    identifier: str,
    scam_type: str,
    score: int,
    confidence: str,
    now: datetime | None = None,
) -> None:
    """Append one line to the staging/live registry."""
    timestamp = now or datetime.now()
    _ensure_live_file(config)
    row = (
        f"{timestamp.isoformat()} | {_sanitize(name) or 'unknown'} | "
        f"{_sanitize(identifier)} | {_sanitize(scam_type)} | {score} | {_sanitize(confidence)}\n"
    )
    with _WRITE_LOCK:
        with config.live_file.open("a", encoding="utf-8") as handle:
            handle.write(row)


def _load_meta(config: RegistryConfig) -> dict:
    if not config.download_meta_file.exists():
        return {}
    try:
        return json.loads(config.download_meta_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _parse_iso(iso_value: str | None) -> datetime | None:
    if not iso_value:
        return None
    try:
        return datetime.fromisoformat(iso_value)
    except ValueError:
        return None

def _pending_rows(config: RegistryConfig) -> list[str]:
    _ensure_live_file(config)
    lines = config.live_file.read_text(encoding="utf-8").splitlines(keepends=True)
    if not lines:
        return []
    return [line for line in lines[1:] if line.strip()]


def _reset_pending_file(config: RegistryConfig) -> None:
    config.live_file.write_text(_header_line(), encoding="utf-8")


def get_download_status(config: RegistryConfig, now: datetime | None = None) -> dict:
    """Return publication cooldown status for the downloadable registry."""
    current = now or datetime.now()
    _ensure_live_file(config)
    published = _ensure_downloadable_file(config)
    meta = _load_meta(config)
    last_published_at = _parse_iso(meta.get("last_published_at"))

    if not last_published_at:
        return {
            "download_available": True,
            "eligible_for_new_publication": True,
            "cooldown_days": config.cooldown_days,
            "last_published_at": None,
            "next_publication_at": None,
            "snapshot_file": str(published),
            "pending_entries": len(_pending_rows(config)),
        }

    next_publication_at = last_published_at + timedelta(days=config.cooldown_days)
    return {
        "download_available": True,
        "eligible_for_new_publication": current >= next_publication_at,
        "cooldown_days": config.cooldown_days,
        "last_published_at": last_published_at.isoformat(),
        "next_publication_at": next_publication_at.isoformat(),
        "snapshot_file": str(published),
        "pending_entries": len(_pending_rows(config)),
    }


def publish_registry_updates_if_due(
    config: RegistryConfig,
    now: datetime | None = None,
    *,
    force: bool = False,
) -> dict:
    """Publish staged entries into the downloadable file when cooldown allows it."""
    current = now or datetime.now()
    status = get_download_status(config, now=current)
    can_publish = force or status["eligible_for_new_publication"]
    published_file = _ensure_downloadable_file(config)
    appended_entries = 0
    published_this_call = False

    if can_publish:
        rows = _pending_rows(config)
        with _WRITE_LOCK:
            if rows:
                with published_file.open("a", encoding="utf-8") as handle:
                    handle.writelines(rows)
                appended_entries = len(rows)
                _reset_pending_file(config)
                published_this_call = True

                config.download_meta_file.parent.mkdir(parents=True, exist_ok=True)
                config.download_meta_file.write_text(
                    json.dumps(
                        {
                            "last_published_at": current.isoformat(),
                            "snapshot_file": str(published_file),
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )

    latest = get_download_status(config, now=current)
    latest["published_this_call"] = published_this_call
    latest["publish_allowed_now"] = can_publish
    latest["appended_entries"] = appended_entries
    return latest


def setup_downloadable_snapshot(config: RegistryConfig, now: datetime | None = None) -> Path:
    """Backward-compatible helper returning the always-downloadable file path."""
    publish_registry_updates_if_due(config, now=now)
    return _ensure_downloadable_file(config)
