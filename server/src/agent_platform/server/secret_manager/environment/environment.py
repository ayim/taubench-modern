import os

from structlog import get_logger

from agent_platform.core.utils.encryption.aes_gcm import AESGCM2
from agent_platform.core.utils.encryption.envelope import StaticKeyEnvelopeEncryption
from agent_platform.server.secret_manager.base import BaseSecretManager

logger = get_logger(__name__)


class EnvironmentSecretManager(BaseSecretManager):
    """Environment variable-based secret manager with hardcoded fallback."""

    FALLBACK_KEY = bytes.fromhex("6fb689e35a85aaa6ca3f8726350c9ec8a681156db9f51cf8faf0264c3146e6c3")

    def __init__(self):
        self.encryption_key: bytes = b""
        self._envelope_encryption: StaticKeyEnvelopeEncryption | None = None
        self.setup()

    def setup(self):
        """Load encryption key from environment variable or use fallback."""
        key = self._load_key_from_environment()

        # Use fallback only if environment variable is not set or empty
        if key is None or key.strip() == "":
            self._use_fallback_key()
            return

        # If environment variable has content, it MUST be valid hex - fail brutally if not
        self._is_valid_key(key)  # Raises exception if invalid
        self.encryption_key = self._convert_key_to_bytes(key)

        # Initialize envelope encryption
        self._envelope_encryption = StaticKeyEnvelopeEncryption(self.encryption_key)

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
            raise ValueError(
                f"Key must be exactly {AESGCM2.VALID_KEY_SIZE} bytes, got {len(decoded)} bytes"
            )
        return decoded

    def _load_key_from_environment(self) -> str | None:
        """Load key from environment variable, return None if not set."""
        key = os.getenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY")
        if key is None:
            logger.warning(
                "SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY environment variable not set. "
                "Using fallback key."
            )
        return key

    def _use_fallback_key(self):
        """Use hardcoded fallback key with warning."""
        logger.warning("Using hardcoded fallback key. This is NOT secure for production use!")
        self.encryption_key = self.FALLBACK_KEY
        self._envelope_encryption = StaticKeyEnvelopeEncryption(self.encryption_key)

    def store(self, data: str) -> str:
        """Store data using envelope encryption and return the encrypted result."""
        if self._envelope_encryption is None:
            raise RuntimeError("Secret manager not properly initialized")

        return self._envelope_encryption.encrypt(data)

    def fetch(self, encrypted_data: str) -> str:
        """Fetch and decrypt data using envelope encryption."""
        if self._envelope_encryption is None:
            raise RuntimeError("Secret manager not properly initialized")

        return self._envelope_encryption.decrypt(encrypted_data)
