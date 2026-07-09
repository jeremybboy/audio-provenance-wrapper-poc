from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path


def utc_timestamp(timestamp: float | None = None) -> str:
    """ISO 8601 UTC timestamp. Uses current time if *timestamp* is None."""
    if timestamp is None:
        timestamp = time.time()
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    """SHA-256 hex digest of a file, read in 1 MB chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def append_jsonl(path: Path, obj: dict[str, object]) -> None:
    """Append a single JSON object as one line to a JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        json.dump(obj, f, separators=(",", ":"))
        f.write("\n")
