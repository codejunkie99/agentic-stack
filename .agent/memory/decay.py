"""Archive old low-salience entries instead of deleting. Git history keeps everything."""
import os, json, datetime
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "harness"))
from salience import salience_score

DECAY_DAYS = 90
SALIENCE_FLOOR = 2.0


def decay_old_entries(entries, archive_dir):
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=DECAY_DAYS)
    kept, archived = [], []
    for e in entries:
        ts_str = e.get("timestamp", "")
        try:
            ts = datetime.datetime.fromisoformat(ts_str)
            # Normalise to UTC — entries may be naive (no tz) or aware.
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=datetime.timezone.utc)
        except ValueError:
            kept.append(e)
            continue
        if ts < cutoff and salience_score(e) < SALIENCE_FLOOR:
            archived.append(e)
        else:
            kept.append(e)

    if archived:
        os.makedirs(archive_dir, exist_ok=True)
        # UTC date so archive filenames align with the UTC cutoff above.
        today_utc = datetime.datetime.now(datetime.timezone.utc).date()
        path = os.path.join(archive_dir, f"archive_{today_utc}.jsonl")
        with open(path, "a") as f:
            for e in archived:
                f.write(json.dumps(e) + "\n")
    return kept, archived
