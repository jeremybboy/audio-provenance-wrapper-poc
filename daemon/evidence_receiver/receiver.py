from __future__ import annotations

import argparse
import json
import logging
import socket
from datetime import datetime, timezone
from pathlib import Path

from .taxonomy import validate_event

log = logging.getLogger(__name__)


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class EvidenceReceiver:

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 9876,
        evidence_path: Path = Path("evidence/plugin_events.jsonl"),
    ) -> None:
        self.host = host
        self.port = port
        self.evidence_path = evidence_path.expanduser()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((host, port))
        self.event_count = 0

    def process_packet(self, data: bytes) -> dict[str, object] | None:
        try:
            event = json.loads(data.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

        valid, error = validate_event(event)
        if not valid:
            log.warning("Invalid event: %s", error)
            return None

        event["received_at"] = utc_timestamp()
        self._write_event(event)
        self.event_count += 1
        return event

    def _write_event(self, event: dict[str, object]) -> None:
        self.evidence_path.parent.mkdir(parents=True, exist_ok=True)
        with self.evidence_path.open("a", encoding="utf-8") as f:
            json.dump(event, f, separators=(",", ":"))
            f.write("\n")

    def run_forever(self) -> None:
        self.evidence_path.parent.mkdir(parents=True, exist_ok=True)
        log.info("Listening on %s:%d; writing %s", self.host, self.port, self.evidence_path)
        while True:
            data, _addr = self.sock.recvfrom(4096)
            event = self.process_packet(data)
            if event is not None:
                log.debug("Received: %s", event.get("event_type"))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Receive plugin observation events via UDP and write evidence JSONL.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to.")
    parser.add_argument("--port", type=int, default=9876, help="UDP port to listen on.")
    parser.add_argument(
        "--evidence-file",
        type=Path,
        default=Path("evidence/plugin_events.jsonl"),
        help="JSONL output path.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args(argv or [])
    receiver = EvidenceReceiver(args.host, args.port, args.evidence_file)
    try:
        receiver.run_forever()
    except KeyboardInterrupt:
        return 0
    return 0
