import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import registry
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


def test_publish_keeps_concurrent_append_as_pending_entry(tmp_path):
    config = RegistryConfig(
        live_file=tmp_path / "live.txt",
        download_dir=tmp_path / "downloads",
        download_meta_file=tmp_path / "meta.json",
        cooldown_days=30,
    )
    base_time = datetime(2026, 1, 1, 8, 0, 0)

    append_registry_entry(
        config,
        name="Scam Account",
        identifier="@scammer1",
        scam_type="payment-redirect",
        score=88,
        confidence="HIGH",
        now=base_time,
    )

    snapshot_started = threading.Event()
    original_pending_rows = registry._pending_rows
    call_count = 0

    def delayed_pending_rows(cfg):
        nonlocal call_count
        call_count += 1
        rows = original_pending_rows(cfg)
        if call_count == 2:
            snapshot_started.set()
            # Delay the in-lock snapshot call inside publication.
            time.sleep(0.2)
        return rows

    result_holder = {}

    def run_publish():
        result_holder["result"] = publish_registry_updates_if_due(config, now=base_time)

    with patch("registry._pending_rows", side_effect=delayed_pending_rows):
        publisher = threading.Thread(target=run_publish)
        publisher.start()
        assert snapshot_started.wait(timeout=1.0)

        # This append races with publication and must not be lost.
        append_registry_entry(
            config,
            name="Scam Account 2",
            identifier="@scammer2",
            scam_type="adult-payment-funnel",
            score=95,
            confidence="HIGH",
            now=base_time + timedelta(seconds=1),
        )

        publisher.join(timeout=2.0)

    publish_result = result_holder["result"]
    assert publish_result["published_this_call"] is True
    assert publish_result["appended_entries"] == 1

    status_after = get_download_status(config, now=base_time)
    assert status_after["pending_entries"] == 1

    live_contents = config.live_file.read_text(encoding="utf-8")
    download_contents = (config.download_dir / config.downloadable_filename).read_text(encoding="utf-8")
    assert "@scammer2" in live_contents
    assert "@scammer2" not in download_contents
