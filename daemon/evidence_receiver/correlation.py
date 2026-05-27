from __future__ import annotations


class SampleCorrelator:
    """Match sample audio fingerprints against plugin stream features.

    Registers sample fingerprints (from the filesystem watcher) and checks
    incoming buffer_hash stream features for approximate matches.  A match
    produces an ``ingredient_correlation`` event with proof_level ``inferred``.
    """

    def __init__(
        self,
        tolerance_rms: float = 0.1,
        tolerance_zcr: float = 0.15,
    ) -> None:
        self.sample_fingerprints: dict[str, dict[str, float | None]] = {}
        self.tolerance_rms = tolerance_rms
        self.tolerance_zcr = tolerance_zcr

    def register_sample(self, sha256: str, fingerprint: dict[str, float | None]) -> None:
        """Store a sample's audio fingerprint for future correlation checks."""
        self.sample_fingerprints[sha256] = fingerprint

    def check_correlation(
        self, stream_features: dict[str, object]
    ) -> list[dict[str, object]]:
        """Return correlation matches for a single stream observation window."""
        matches: list[dict[str, object]] = []
        stream_rms = stream_features.get("rms_level", 0)
        stream_zcr = stream_features.get("zero_crossing_rate", 0)

        if not isinstance(stream_rms, (int, float)) or not isinstance(
            stream_zcr, (int, float)
        ):
            return matches

        for sha256, fp in self.sample_fingerprints.items():
            sample_rms = fp.get("rms")
            sample_zcr = fp.get("zero_crossing_rate")

            if sample_rms is None or sample_zcr is None:
                continue

            rms_diff = abs(float(stream_rms) - float(sample_rms))
            zcr_diff = abs(float(stream_zcr) - float(sample_zcr))

            if rms_diff < self.tolerance_rms and zcr_diff < self.tolerance_zcr:
                confidence = max(
                    0.0,
                    1.0
                    - (rms_diff / self.tolerance_rms + zcr_diff / self.tolerance_zcr)
                    / 2.0,
                )
                matches.append(
                    {
                        "sample_sha256": sha256,
                        "confidence": round(confidence, 3),
                        "rms_diff": round(rms_diff, 6),
                        "zcr_diff": round(zcr_diff, 6),
                    }
                )

        return matches
