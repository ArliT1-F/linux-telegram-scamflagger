from datetime import datetime, timedelta
from pathlib import Path

from registry import (
    RegistryConfig,
    append_registry_entry,
    get_download_status,
    publish_registry_updates_if_due,
)


def test_registry_download_always_available_and_monthly_publication(tmp_path):
    config = RegistryConfig(
        live_file=tmp_path / "live.txt",
        download_dir=tmp_path / "downloads",
        download_meta_file=tmp_path / "meta.json",
        cooldown_days=30,
    )
    base_time = datetime(2026, 1, 1, 8, 0, 0)

    status = get_download_status(config, now=base_time)
    assert status["download_available"] is True
    assert status["eligible_for_new_publication"] is True
    assert status["pending_entries"] == 0
    assert Path(status["snapshot_file"]).exists()

    append_registry_entry(
        config,
        name="Scam Account",
        identifier="@scammer1",
        scam_type="payment-redirect",
        score=88,
        confidence="HIGH",
        now=base_time,
    )
    status_after_entry = get_download_status(config, now=base_time)
    assert status_after_entry["pending_entries"] == 1

    first_publish = publish_registry_updates_if_due(config, now=base_time)
    assert first_publish["published_this_call"] is True
    assert first_publish["appended_entries"] == 1
    assert first_publish["pending_entries"] == 0

    # Add a new entry before cooldown ends: should remain staged.
    append_registry_entry(
        config,
        name="Scam Account 2",
        identifier="@scammer2",
        scam_type="adult-payment-funnel",
        score=95,
        confidence="HIGH",
        now=base_time + timedelta(days=1),
    )
    blocked = publish_registry_updates_if_due(config, now=base_time + timedelta(days=1))
    assert blocked["published_this_call"] is False
    assert blocked["publish_allowed_now"] is False
    assert blocked["pending_entries"] == 1
    assert blocked["download_available"] is True

    # After cooldown, publication is allowed again.
    second_publish = publish_registry_updates_if_due(config, now=base_time + timedelta(days=31))
    assert second_publish["published_this_call"] is True
    assert second_publish["appended_entries"] == 1
    assert second_publish["pending_entries"] == 0

