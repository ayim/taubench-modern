from datetime import UTC, datetime

from agent_platform.core.runbook import Runbook


def test_model_dump_roundtrip_preserves_updated_at() -> None:
    timestamp = datetime(2024, 1, 1, 12, 30, tzinfo=UTC)
    runbook = Runbook(raw_text="Hello", content=[], updated_at=timestamp)

    dumped = runbook.model_dump()

    restored = Runbook.model_validate(dumped, fallback_updated_at=timestamp)

    assert dumped["updated_at"] == timestamp.isoformat()
    assert restored.updated_at == timestamp


def test_model_validate_uses_fallback_when_missing_updated_at() -> None:
    fallback = datetime(2024, 5, 1, 10, 15, tzinfo=UTC)

    runbook = Runbook.model_validate(
        {"raw_text": "Hi", "content": []},
        fallback_updated_at=fallback,
    )

    assert runbook.updated_at == fallback


def test_model_validate_parses_iso_string_with_timezone() -> None:
    timestamp_str = "2024-05-01T10:15:30+02:00"
    expected = datetime(2024, 5, 1, 8, 15, 30, tzinfo=UTC)

    runbook = Runbook.model_validate(
        {"raw_text": "Hi", "content": [], "updated_at": timestamp_str},
        fallback_updated_at=datetime(2024, 5, 1, 9, 0, tzinfo=UTC),
    )

    assert runbook.updated_at == expected


def test_model_validate_parses_naive_string_as_utc() -> None:
    timestamp_str = "2024-05-01T10:15:30"
    expected = datetime(2024, 5, 1, 10, 15, 30, tzinfo=UTC)

    runbook = Runbook.model_validate(
        {"raw_text": "Hi", "content": [], "updated_at": timestamp_str},
        fallback_updated_at=datetime(2024, 5, 1, 9, 0, tzinfo=UTC),
    )

    assert runbook.updated_at == expected


def test_model_validate_accepts_datetime_objects() -> None:
    fallback = datetime(2024, 5, 1, 9, 0, tzinfo=UTC)
    naive_dt = datetime(2024, 5, 1, 10, 15, 30)
    aware_dt = datetime(2024, 5, 1, 10, 15, 30, tzinfo=UTC)

    naive_runbook = Runbook.model_validate(
        {"raw_text": "Hi", "content": [], "updated_at": naive_dt},
        fallback_updated_at=fallback,
    )
    aware_runbook = Runbook.model_validate(
        {"raw_text": "Hi", "content": [], "updated_at": aware_dt},
        fallback_updated_at=fallback,
    )

    assert naive_runbook.updated_at == datetime(2024, 5, 1, 10, 15, 30, tzinfo=UTC)
    assert aware_runbook.updated_at == aware_dt


def test_model_validate_uses_fallback_on_invalid_timestamp() -> None:
    fallback = datetime(2024, 5, 1, 9, 0, tzinfo=UTC)

    runbook = Runbook.model_validate(
        {"raw_text": "Hi", "content": [], "updated_at": "invalid"},
        fallback_updated_at=fallback,
    )

    assert runbook.updated_at == fallback


def test_model_validate_normalises_fallback_datetime() -> None:
    fallback = datetime(2024, 5, 1, 9, 0, 0)

    runbook = Runbook.model_validate(
        {"raw_text": "Hi", "content": []},
        fallback_updated_at=fallback,
    )

    assert runbook.updated_at == datetime(2024, 5, 1, 9, 0, 0)
