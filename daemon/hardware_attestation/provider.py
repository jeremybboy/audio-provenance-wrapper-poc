from __future__ import annotations

import abc
import hashlib
import logging
import time
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class DeviceIdentity:
    """Unique hardware-bound identity for this machine."""

    device_id: str
    public_key_hex: str
    algorithm: str
    created_at_ms: int


@dataclass(frozen=True)
class HardwareBinding:
    """A hash chain root sealed to hardware."""

    chain_root_hash: str
    device_id: str
    monotonic_counter: int
    clock_ms: int
    signature_hex: str
    public_key_hex: str


@dataclass(frozen=True)
class HardwareCosignature:
    """Self-entangled hardware cosignature following the CPoE pattern.

    Each cosignature chains the previous one, making forgery of checkpoint N
    require valid signatures for all preceding checkpoints.

    entangled_hash = SHA256(
        domain_separator
        || content_hash
        || software_signature
        || hardware_clock_ms
        || monotonic_counter
        || device_id
        || previous_cosignature
    )
    """

    entangled_hash: str
    content_hash: str
    hardware_clock_ms: int
    monotonic_counter: int
    device_id: str
    signature_hex: str
    previous_cosignature_hash: str

    DOMAIN_SEPARATOR = b"apw-hw-cosign-v1"


class HardwareProvider(abc.ABC):
    """Abstract interface for hardware security modules.

    Implementations:
        SecureEnclaveProvider - macOS Secure Enclave via Security.framework
        TpmProvider           - Linux TPM 2.0 via tpm2-tools or tss2
        SoftwareProvider      - Fallback using filesystem keys (NOT attestable)
    """

    @abc.abstractmethod
    def device_identity(self) -> DeviceIdentity:
        """Return the hardware-bound device identity."""

    @abc.abstractmethod
    def sign(self, data: bytes) -> bytes:
        """Sign data with the hardware-bound private key.

        The private key never leaves the hardware module.
        """

    @abc.abstractmethod
    def verify(self, data: bytes, signature: bytes) -> bool:
        """Verify a signature against the hardware public key."""

    @abc.abstractmethod
    def seal(self, plaintext: bytes) -> bytes:
        """Encrypt data such that only this hardware can decrypt it.

        Sealed data is bound to the current device and platform state.
        """

    @abc.abstractmethod
    def unseal(self, sealed: bytes) -> bytes:
        """Decrypt hardware-sealed data."""

    @abc.abstractmethod
    def monotonic_counter(self) -> int:
        """Return a hardware-backed monotonic counter value.

        This counter increments on each call and cannot be rolled back.
        Used to detect replay attacks on the hash chain.
        """

    @abc.abstractmethod
    def clock_ms(self) -> int:
        """Return the hardware-attested clock value in milliseconds.

        On TPM this is the TPM clock; on Secure Enclave this is the
        monotonic system clock attested by the SE.
        """

    def bind_chain_root(self, chain_root_hash: str) -> HardwareBinding:
        """Bind a hash chain root to this hardware device.

        Creates a signed attestation that this specific hash chain root
        was produced on this specific device at this specific counter value.
        """
        identity = self.device_identity()
        counter = self.monotonic_counter()
        clock = self.clock_ms()

        payload = (
            chain_root_hash.encode()
            + identity.device_id.encode()
            + counter.to_bytes(8, "big")
            + clock.to_bytes(8, "big")
        )
        signature = self.sign(payload)

        return HardwareBinding(
            chain_root_hash=chain_root_hash,
            device_id=identity.device_id,
            monotonic_counter=counter,
            clock_ms=clock,
            signature_hex=signature.hex(),
            public_key_hex=identity.public_key_hex,
        )

    def cosign_checkpoint(
        self,
        content_hash: str,
        software_signature: str,
        previous_cosignature_hash: str,
    ) -> HardwareCosignature:
        """Create a self-entangled hardware cosignature for a checkpoint.

        Each cosignature includes the hash of the previous one, creating
        a chain that is bound to both software evidence and hardware state.
        """
        identity = self.device_identity()
        counter = self.monotonic_counter()
        clock = self.clock_ms()

        entangle_input = (
            HardwareCosignature.DOMAIN_SEPARATOR
            + content_hash.encode()
            + software_signature.encode()
            + clock.to_bytes(8, "big")
            + counter.to_bytes(8, "big")
            + identity.device_id.encode()
            + previous_cosignature_hash.encode()
        )
        entangled_hash = hashlib.sha256(entangle_input).hexdigest()
        signature = self.sign(entangled_hash.encode())

        return HardwareCosignature(
            entangled_hash=entangled_hash,
            content_hash=content_hash,
            hardware_clock_ms=clock,
            monotonic_counter=counter,
            device_id=identity.device_id,
            signature_hex=signature.hex(),
            previous_cosignature_hash=previous_cosignature_hash,
        )


class SecureEnclaveProvider(HardwareProvider):
    """macOS Secure Enclave via Security.framework.

    Requires pyobjc-framework-Security or ctypes bindings to:
        SecKeyCreateRandomKey (kSecAttrTokenIDSecureEnclave)
        SecKeyCreateSignature (kSecKeyAlgorithmECDSASignatureMessageX962SHA256)
        SecKeyVerifySignature

    The private key is created with kSecAttrIsPermanent=True and stored
    in the Secure Enclave. It never leaves the hardware.

    Stub: all methods raise NotImplementedError.
    """

    def device_identity(self) -> DeviceIdentity:
        raise NotImplementedError("Secure Enclave integration not yet implemented")

    def sign(self, data: bytes) -> bytes:
        raise NotImplementedError("Secure Enclave integration not yet implemented")

    def verify(self, data: bytes, signature: bytes) -> bool:
        raise NotImplementedError("Secure Enclave integration not yet implemented")

    def seal(self, plaintext: bytes) -> bytes:
        raise NotImplementedError("Secure Enclave integration not yet implemented")

    def unseal(self, sealed: bytes) -> bytes:
        raise NotImplementedError("Secure Enclave integration not yet implemented")

    def monotonic_counter(self) -> int:
        raise NotImplementedError("Secure Enclave integration not yet implemented")

    def clock_ms(self) -> int:
        raise NotImplementedError("Secure Enclave integration not yet implemented")


class TpmProvider(HardwareProvider):
    """Linux TPM 2.0 via tpm2-tools CLI or tss2 Python bindings.

    Uses the TPM endorsement key hierarchy:
        EK (Endorsement Key)  - device identity, not directly usable
        SRK (Storage Root Key) - parent for sealing
        AK (Attestation Key)  - signing for quotes and attestations

    Monotonic counter: TPM2_NV_Increment on a reserved NV index.
    Clock: TPM2_ReadClock for attested time.

    Stub: all methods raise NotImplementedError.
    """

    def device_identity(self) -> DeviceIdentity:
        raise NotImplementedError("TPM 2.0 integration not yet implemented")

    def sign(self, data: bytes) -> bytes:
        raise NotImplementedError("TPM 2.0 integration not yet implemented")

    def verify(self, data: bytes, signature: bytes) -> bool:
        raise NotImplementedError("TPM 2.0 integration not yet implemented")

    def seal(self, plaintext: bytes) -> bytes:
        raise NotImplementedError("TPM 2.0 integration not yet implemented")

    def unseal(self, sealed: bytes) -> bytes:
        raise NotImplementedError("TPM 2.0 integration not yet implemented")

    def monotonic_counter(self) -> int:
        raise NotImplementedError("TPM 2.0 integration not yet implemented")

    def clock_ms(self) -> int:
        raise NotImplementedError("TPM 2.0 integration not yet implemented")


class SoftwareProvider(HardwareProvider):
    """Fallback provider using filesystem-stored Ed25519 keys.

    NOT attestable. Evidence produced with this provider carries proof level
    'directly_observed' for the hash chain but 'unknown_unobserved' for
    hardware binding. An auditor can verify chain integrity but not that
    the chain was produced on a specific device.

    Useful for development and for platforms without hardware security.
    """

    def __init__(self, key_path: Path = Path("~/.apw/device_key.pem")) -> None:
        self.key_path = key_path.expanduser()

    def device_identity(self) -> DeviceIdentity:
        raise NotImplementedError("Software key provider not yet implemented")

    def sign(self, data: bytes) -> bytes:
        raise NotImplementedError("Software key provider not yet implemented")

    def verify(self, data: bytes, signature: bytes) -> bool:
        raise NotImplementedError("Software key provider not yet implemented")

    def seal(self, plaintext: bytes) -> bytes:
        raise NotImplementedError("Software key provider not yet implemented")

    def unseal(self, sealed: bytes) -> bytes:
        raise NotImplementedError("Software key provider not yet implemented")

    def monotonic_counter(self) -> int:
        raise NotImplementedError("Software key provider not yet implemented")

    def clock_ms(self) -> int:
        return int(time.time() * 1000)


def detect_provider() -> HardwareProvider:
    """Auto-detect the best available hardware provider for this platform.

    Priority: Secure Enclave > TPM 2.0 > Software fallback.
    """
    import platform

    system = platform.system()

    if system == "Darwin":
        log.info("macOS detected; Secure Enclave provider selected (stub)")
        return SecureEnclaveProvider()

    if system == "Linux":
        if Path("/dev/tpm0").exists() or Path("/dev/tpmrm0").exists():
            log.info("TPM 2.0 device detected; TPM provider selected (stub)")
            return TpmProvider()

    log.warning("No hardware security module detected; using software fallback")
    return SoftwareProvider()
