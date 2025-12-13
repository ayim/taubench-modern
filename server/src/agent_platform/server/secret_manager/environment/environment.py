import hashlib
import os

from structlog import get_logger

from agent_platform.core.utils.encryption.aes_gcm import AESGCM2
from agent_platform.core.utils.encryption.envelope import StaticKeyEnvelopeEncryption
from agent_platform.server.secret_manager.base import BaseSecretManager

logger = get_logger(__name__)


class EnvironmentSecretManager(BaseSecretManager):
    """Environment variable-based secret manager with hardcoded fallback."""

    def __init__(self):
        self.encryption_key: bytes = b""
        self._envelope_encryption: StaticKeyEnvelopeEncryption | None = None
        self._fallback_envelope_encryption: StaticKeyEnvelopeEncryption | None = None
        self.setup()

    def setup(self):
        """Load encryption key from environment variable or use fallback."""
        key = self._load_key_from_environment()

        # Always create fallback envelope encryption instance
        self._fallback_envelope_encryption = StaticKeyEnvelopeEncryption(self.FALLBACK_KEY, key_id="fallback")

        # Use fallback only if environment variable is not set or empty
        if key is None or key.strip() == "":
            self._use_fallback_key()
            return

        # If environment variable has content, it MUST be valid hex - fail brutally if not
        self._is_valid_key(key)  # Raises exception if invalid
        self.encryption_key = self._convert_key_to_bytes(key)

        # Generate key_id using SHA256 hash of the key
        key_id = hashlib.sha256(self.encryption_key).hexdigest()

        # Initialize primary envelope encryption
        self._envelope_encryption = StaticKeyEnvelopeEncryption(self.encryption_key, key_id=key_id)

    def _is_valid_key(self, key: str) -> bool:
        """Check if the key is valid hex-encoded 32-byte key."""
        try:
            decoded = bytes.fromhex(key)
            return len(decoded) == AESGCM2.VALID_KEY_SIZE
        except ValueError:
            msg = (
                "SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY contains invalid hex data. "
                f"Expected 64 hex characters (32 bytes), got: {key[:20]}..."
            )
            raise ValueError(msg) from None

    def _convert_key_to_bytes(self, key: str) -> bytes:
        """Convert hex-encoded string key to bytes."""
        decoded = bytes.fromhex(key)
        if len(decoded) != AESGCM2.VALID_KEY_SIZE:
            raise ValueError(f"Key must be exactly {AESGCM2.VALID_KEY_SIZE} bytes, got {len(decoded)} bytes")
        return decoded

    def _load_key_from_environment(self) -> str | None:
        """Load key from environment variable, return None if not set."""
        key = os.getenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY")
        if key is None:
            logger.warning("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY environment variable not set. Using fallback key.")
        return key

    def _use_fallback_key(self):
        """Use hardcoded fallback key with warning."""
        logger.warning("Using hardcoded fallback key. This is NOT secure for production use!")
        self.encryption_key = self.FALLBACK_KEY
        # Use the fallback envelope encryption as the primary one
        self._envelope_encryption = self._fallback_envelope_encryption

    def store(self, data: str) -> str:
        """Store data using envelope encryption and return the encrypted result."""
        if self._envelope_encryption is None:
            raise RuntimeError("Secret manager not properly initialized")

        return self._envelope_encryption.encrypt(data)

    def fetch(self, encrypted_data: str) -> str:
        """Fetch and decrypt data using envelope encryption."""
        if self._envelope_encryption is None:
            raise RuntimeError("Secret manager not properly initialized")

        # Parse metadata to check which key was used for encryption
        from agent_platform.core.utils.encryption.envelope import EnvelopeEncryptionResult

        try:
            envelope_result = EnvelopeEncryptionResult.from_json(encrypted_data)
            encrypted_key_id = envelope_result.metadata.key_id

            # If data was encrypted with fallback key, use fallback to decrypt
            if encrypted_key_id == "fallback" and self._fallback_envelope_encryption is not None:
                return self._fallback_envelope_encryption.decrypt(encrypted_data)

        except Exception as e:
            # If metadata parsing fails, fall back to primary encryption
            logger.error(f"Metadata parsing failed, falling back to primary encryption: {e}")

        # Default to primary encryption for both non-fallback keys and parsing failures
        return self._envelope_encryption.decrypt(encrypted_data)
