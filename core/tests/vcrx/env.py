import os


def env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip() in {"1", "true", "True", "YES", "yes", "on", "ON"}


def debug_enabled() -> bool:
    return env_bool("VCR_DEBUG", False)


def debug(msg: str) -> None:
    if debug_enabled():
        try:
            print(msg)
        except Exception:
            pass


def get_vcr_record_mode():
    """
    Parse VCR record mode from env (VCR_RECORD), default 'none'.
    Returns vcr.record_mode.RecordMode enum.
    """
    from vcr.record_mode import RecordMode

    raw = (os.getenv("VCR_RECORD", "none") or "none").lower().strip()
    mapping = {
        "none": RecordMode.NONE,
        "new_episodes": RecordMode.NEW_EPISODES,
        "once": RecordMode.ONCE,
        "all": RecordMode.ALL,
        # defensive aliases
        "off": RecordMode.NONE,
        "disabled": RecordMode.NONE,
    }
    try:
        return mapping[raw]
    except KeyError as exc:
        raise ValueError(f"Invalid VCR record mode: {raw!r}") from exc
