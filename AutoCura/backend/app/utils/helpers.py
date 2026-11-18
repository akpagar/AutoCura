"""
AutoCura - Generic Helper Functions

Small, dependency-light utilities shared across modules. Anything
domain-specific (ML, recovery, monitoring) belongs in its own module,
not here.
"""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Timezone-aware current UTC timestamp, used consistently for DB writes."""
    return datetime.now(UTC)


def seconds_since(reference: datetime) -> float:
    """
    Seconds elapsed since `reference`, robust to whether the datetime
    read back from the database is timezone-aware or naive. SQLite (and
    a plain SQLAlchemy DateTime column without timezone=True on other
    backends) strips tzinfo on round-trip even though utc_now() always
    *writes* a UTC-aware value -- so a raw `utc_now() - db_value`
    subtraction raises "can't subtract offset-naive and offset-aware
    datetimes" the moment the app runs against a real database instead
    of an in-memory object. Every column written via utc_now() holds a
    UTC instant, so a naive value read back is safely assumed to be UTC.
    """
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=UTC)
    return (utc_now() - reference).total_seconds()


def clamp(value: float, low: float, high: float) -> float:
    """Clamp `value` into the inclusive range [low, high]."""
    return max(low, min(value, high))


def safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Division that returns `default` instead of raising on divide-by-zero."""
    if denominator == 0:
        return default
    return numerator / denominator


def round2(value: float) -> float:
    """Round a float to 2 decimal places -- used for consistent API output."""
    return round(value, 2)
