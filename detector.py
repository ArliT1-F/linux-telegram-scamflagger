"""Reusable scam/promo detection logic used by API and listener."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


DEFAULT_KEYWORDS = {
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
    "t.me/": 20,
}

PAYMENT_KEYWORDS = {
    "paypal",
    "cashapp",
    "venmo",
    "bitcoin",
    "btc",
    "usdt",
    "paid",
    "payment",
    "pay me",
}
REDIRECT_KEYWORDS = {
    "whatsapp",
    "telegram.me",
    "t.me/",
    "snapchat",
    "instagram",
    "dm me",
    "add me on",
}
ADULT_KEYWORDS = {
    "onlyfans",
    "only fans",
    "escort",
    "cam girl",
    "nudes",
    "premium content",
}

PHONE_REGEX = re.compile(r"\+?\d[\d\s\-().]{7,}")
LINK_REGEX = re.compile(r"https?://\S+|wa\.me/\S+|t\.me/\S+")


@dataclass(frozen=True)
class DetectorConfig:
    save_threshold: int = 30
    long_message_threshold: int = 200
    long_message_score: int = 15
    phone_score: int = 40
    link_score: int = 25
    combo_bonus: int = 20
    keyword_scores: dict[str, int] = field(default_factory=lambda: DEFAULT_KEYWORDS.copy())


DEFAULT_CONFIG = DetectorConfig()


def analyze_message(text: str, config: DetectorConfig | None = None) -> tuple[int, list[str]]:
    """Analyze a message and return score + reasons."""
    active_config = config or DEFAULT_CONFIG

    score = 0
    reasons: list[str] = []
    lowered = text.lower()

    payment = False
    redirect = False
    adult = False

    for keyword, points in active_config.keyword_scores.items():
        if keyword in lowered:
            score += points
            reasons.append(f"{keyword} (+{points})")

            if keyword in PAYMENT_KEYWORDS:
                payment = True
            if keyword in REDIRECT_KEYWORDS:
                redirect = True
            if keyword in ADULT_KEYWORDS:
                adult = True

    if PHONE_REGEX.search(text):
        score += active_config.phone_score
        reasons.append(f"phone number (+{active_config.phone_score})")
        redirect = True

    if LINK_REGEX.search(text):
        score += active_config.link_score
        reasons.append(f"external link (+{active_config.link_score})")
        redirect = True

    if len(text) > active_config.long_message_threshold:
        score += active_config.long_message_score
        reasons.append(f"long message (+{active_config.long_message_score})")

    if payment and redirect:
        score += active_config.combo_bonus
        reasons.append(f"payment + redirect combo (+{active_config.combo_bonus})")

    if adult and redirect:
        score += active_config.combo_bonus
        reasons.append(f"adult + redirect combo (+{active_config.combo_bonus})")

    return min(score, 100), reasons


def confidence_label(score: int) -> str:
    """Map score to LOW/MEDIUM/HIGH label."""
    if score >= 60:
        return "HIGH"
    if score >= 30:
        return "MEDIUM"
    return "LOW"
