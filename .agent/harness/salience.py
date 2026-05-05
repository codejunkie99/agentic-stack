"""Salience scoring: recent + painful + important + recurring = surface first."""
import datetime


def salience_score(entry: dict) -> float:
    """Weighted score used for episodic retrieval and promotion thresholds."""
    ts = entry.get("timestamp")
    if not ts:
        return 0.0
    try:
        parsed = datetime.datetime.fromisoformat(ts)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=datetime.timezone.utc)
        # Negative age can happen during the naive-→-UTC migration window
        # if a legacy naive-local timestamp now reads as a few hours in the
        # future. Floor at 0 so recency stays in [0, 10] instead of inflating.
        age_days = max(0, (datetime.datetime.now(datetime.timezone.utc) - parsed).days)
    except ValueError:
        age_days = 999
    pain = entry.get("pain_score", 5)
    importance = entry.get("importance", 5)
    recurrence = entry.get("recurrence_count", 1)
    recency = max(0.0, min(10.0, 10.0 - age_days * 0.3))
    return recency * (pain / 10.0) * (importance / 10.0) * min(recurrence, 3)
