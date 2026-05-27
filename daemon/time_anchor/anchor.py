from __future__ import annotations

import abc
import hashlib
import logging
import time
from dataclasses import dataclass

log = logging.getLogger(__name__)

ROUGHTIME_TOLERANCE_MS = 180_000  # 3 minutes, matches CPoE default
TSA_TIMEOUT_SECONDS = 10


@dataclass(frozen=True)
class TimeProof:
    """An externally-verifiable timestamp from an independent time source."""

    source: str
    timestamp_ms: int
    nonce_hex: str
    response_hex: str
    certificate_chain_hex: str | None


@dataclass(frozen=True)
class DualAnchor:
    """Two independent time proofs that must agree within tolerance.

    Following the CPoE pattern: a checkpoint is anchored by BOTH an RFC 3161
    TSA response AND a Roughtime response. An auditor verifies that both
    sources agree within the configured tolerance window. Disagreement
    indicates clock manipulation.
    """

    tsa_proof: TimeProof | None
    roughtime_proof: TimeProof | None
    tolerance_ms: int = ROUGHTIME_TOLERANCE_MS

    @property
    def anchored(self) -> bool:
        return self.tsa_proof is not None or self.roughtime_proof is not None

    @property
    def dual_anchored(self) -> bool:
        return self.tsa_proof is not None and self.roughtime_proof is not None

    @property
    def agreement_ms(self) -> int | None:
        if not self.dual_anchored:
            return None
        return abs(self.tsa_proof.timestamp_ms - self.roughtime_proof.timestamp_ms)

    @property
    def within_tolerance(self) -> bool:
        agreement = self.agreement_ms
        if agreement is None:
            return True
        return agreement <= self.tolerance_ms

    def best_timestamp_ms(self) -> int:
        if self.dual_anchored:
            return (self.tsa_proof.timestamp_ms + self.roughtime_proof.timestamp_ms) // 2
        if self.tsa_proof is not None:
            return self.tsa_proof.timestamp_ms
        if self.roughtime_proof is not None:
            return self.roughtime_proof.timestamp_ms
        return int(time.time() * 1000)


class TimeAnchorProvider(abc.ABC):
    """Abstract interface for external time anchoring."""

    @abc.abstractmethod
    def anchor(self, data_hash: str, nonce: bytes) -> TimeProof:
        """Request a timestamp proof for the given data hash."""

    @abc.abstractmethod
    def verify(self, proof: TimeProof, data_hash: str) -> bool:
        """Verify a timestamp proof against the original data hash."""


class RFC3161Provider(TimeAnchorProvider):
    """RFC 3161 Time-Stamp Authority client.

    Sends a TimeStampReq containing a MessageImprint (SHA-256 hash + nonce)
    to a TSA server and receives a signed TimeStampResp.

    Standard TSA servers:
        - http://timestamp.digicert.com
        - http://tsa.starfieldtech.com
        - http://timestamp.sectigo.com
        - http://zeitstempel.dfn.de

    Wire format (ASN.1 DER):
        TimeStampReq ::= SEQUENCE {
            version         INTEGER { v1(1) },
            messageImprint  MessageImprint,
            nonce           INTEGER OPTIONAL,
            certReq         BOOLEAN DEFAULT FALSE
        }
        MessageImprint ::= SEQUENCE {
            hashAlgorithm   AlgorithmIdentifier,  -- SHA-256
            hashedMessage    OCTET STRING
        }

    The response contains a signed CMS structure with the timestamp token.
    Verification requires checking the CMS signature against the TSA's
    certificate chain.

    Dependencies for implementation:
        - asn1crypto (ASN.1 encoding/decoding)
        - requests or urllib3 (HTTP POST to TSA)
        - cryptography (CMS signature verification)

    Stub: all methods raise NotImplementedError.
    """

    def __init__(self, tsa_url: str = "http://timestamp.digicert.com") -> None:
        self.tsa_url = tsa_url

    def anchor(self, data_hash: str, nonce: bytes) -> TimeProof:
        raise NotImplementedError("RFC 3161 TSA client not yet implemented")

    def verify(self, proof: TimeProof, data_hash: str) -> bool:
        raise NotImplementedError("RFC 3161 TSA verification not yet implemented")


class RoughtimeProvider(TimeAnchorProvider):
    """Roughtime protocol client (draft-ietf-ntp-roughtime).

    Roughtime provides authenticated, approximate time from multiple
    independent servers. Each response includes:
        - MIDP: midpoint timestamp (microseconds since epoch)
        - RADI: radius of uncertainty (microseconds)
        - SIG: Ed25519 signature over (MIDP, RADI, nonce)

    The nonce is typically a blind: SHA-512(previous_reply || new_request).
    This creates a chain of Roughtime responses where each one commits to
    the previous, preventing the server from backdating.

    Standard Roughtime servers:
        - roughtime.cloudflare.com:2002
        - roughtime.sandbox.google.com:2002
        - roughtime.int08h.com:2002

    Dependencies for implementation:
        - ed25519 (signature verification)
        - socket (UDP client)

    Stub: all methods raise NotImplementedError.
    """

    DEFAULT_SERVERS = [
        ("roughtime.cloudflare.com", 2002),
        ("roughtime.sandbox.google.com", 2002),
        ("roughtime.int08h.com", 2002),
    ]

    def __init__(self, servers: list[tuple[str, int]] | None = None) -> None:
        self.servers = servers or self.DEFAULT_SERVERS

    def anchor(self, data_hash: str, nonce: bytes) -> TimeProof:
        raise NotImplementedError("Roughtime client not yet implemented")

    def verify(self, proof: TimeProof, data_hash: str) -> bool:
        raise NotImplementedError("Roughtime verification not yet implemented")


class TimeAnchorService:
    """Coordinates dual time anchoring for hash chain checkpoints.

    Usage:
        service = TimeAnchorService()
        anchor = service.anchor_checkpoint(checkpoint_hash)
        assert anchor.dual_anchored
        assert anchor.within_tolerance
    """

    def __init__(
        self,
        tsa: RFC3161Provider | None = None,
        roughtime: RoughtimeProvider | None = None,
        tolerance_ms: int = ROUGHTIME_TOLERANCE_MS,
    ) -> None:
        self.tsa = tsa or RFC3161Provider()
        self.roughtime = roughtime or RoughtimeProvider()
        self.tolerance_ms = tolerance_ms

    def anchor_checkpoint(self, checkpoint_hash: str) -> DualAnchor:
        """Anchor a checkpoint hash with both RFC 3161 and Roughtime.

        If either source fails, the anchor is still created with whichever
        source succeeded. A missing source is recorded in the evidence as
        a degraded anchor.
        """
        nonce = hashlib.sha256(
            checkpoint_hash.encode() + int(time.time() * 1000).to_bytes(8, "big")
        ).digest()[:16]

        tsa_proof = None
        roughtime_proof = None

        try:
            tsa_proof = self.tsa.anchor(checkpoint_hash, nonce)
        except (NotImplementedError, Exception) as e:
            log.warning("TSA anchoring failed: %s", e)

        try:
            roughtime_proof = self.roughtime.anchor(checkpoint_hash, nonce)
        except (NotImplementedError, Exception) as e:
            log.warning("Roughtime anchoring failed: %s", e)

        anchor = DualAnchor(
            tsa_proof=tsa_proof,
            roughtime_proof=roughtime_proof,
            tolerance_ms=self.tolerance_ms,
        )

        if anchor.dual_anchored and not anchor.within_tolerance:
            log.warning(
                "Time sources disagree by %dms (tolerance: %dms)",
                anchor.agreement_ms,
                self.tolerance_ms,
            )

        return anchor
