from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo


def cutoff_for(zone, dispatch_date):
    day = date.fromisoformat(dispatch_date)
    local = datetime.combine(
        day,
        time.fromisoformat(zone.get("dispatch_time", "09:00")),
        ZoneInfo(zone.get("timezone", "Asia/Kolkata")),
    )
    return (
        (local - timedelta(hours=zone.get("cutoff_hours_before", 0)))
        .astimezone(UTC)
        .isoformat()
    )


def cutoff_passed(pool, at=None):
    return bool(
        pool.get("cutoff_at")
        and datetime.fromisoformat(pool["cutoff_at"]) <= (at or datetime.now(UTC))
    )


def approval_deadline(zone, dispatch_date, at=None):
    at = at or datetime.now(UTC)
    local_end = datetime.combine(
        date.fromisoformat(dispatch_date),
        time(23, 59, 59),
        ZoneInfo(zone.get("timezone", "Asia/Kolkata")),
    ).astimezone(UTC)
    return min(
        at + timedelta(hours=zone.get("approval_hours", 24)), local_end
    ).isoformat()
