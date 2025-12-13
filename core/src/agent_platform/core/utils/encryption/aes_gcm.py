"""
Core AES-GCM encryption implementation using the cryptography library.
"""

import os
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


@dataclass
class EncryptionResult:
    """Result of AES-GCM encryption containing nonce, ciphertext and authentication tag."""

    nonce: bytes
    ciphertext: bytes
    tag: bytes


class AESGCM2:
    """
    AES-GCM wrapper using the `cryptography` library.
    Supports 256-bit keys, optional AAD, and returns nonce, ciphertext, and auth tag separately.
    """

    # Key sizes in bytes (256 bits)
    VALID_KEY_SIZE = 32
    # GCM recommended nonce size in bytes (96 bits)
    NONCE_SIZE = 12
    # GCM authentication tag size in bytes (128 bits)
    TAG_SIZE = 16

    def __init__(self, key: bytes):
        # Key must be 256 bits (32 bytes)
        if len(key) != self.VALID_KEY_SIZE:
            raise ValueError("Key must be 256 bits (32 bytes).")
        self.key = key
        self.aesgcm = AESGCM(self.key)

    def encrypt(self, plaintext: bytes, associated_data: bytes | None = None) -> EncryptionResult:
        """
        Encrypts plaintext with AES-GCM.

        :param plaintext: Data to encrypt.
        :param associated_data: Optional AAD for authentication.
        :return: EncryptionResult containing nonce, ciphertext, and tag.
        """
        # 96-bit (12-byte) nonce is recommended for GCM
        nonce = os.urandom(self.NONCE_SIZE)
        # AESGCM.encrypt returns ciphertext || tag (16 bytes)
        ct_and_tag = self.aesgcm.encrypt(nonce, plaintext, associated_data)
        ciphertext, tag = ct_and_tag[: -self.TAG_SIZE], ct_and_tag[-self.TAG_SIZE :]
        return EncryptionResult(nonce=nonce, ciphertext=ciphertext, tag=tag)

    def decrypt(self, nonce: bytes, ciphertext: bytes, tag: bytes, associated_data: bytes | None = None) -> bytes:
        """
        Decrypts and verifies AES-GCM ciphertext.

        :param nonce: The 12-byte nonce used during encryption.
        :param ciphertext: The encrypted data (without the tag).
        :param tag: The 16-byte authentication tag.
        :param associated_data: The same AAD used during encryption.
        :return: The original plaintext.
        :raises InvalidTag: If authentication fails.
        :raises ValueError: If input parameters are invalid.
        """
        # Validate nonce length (must be 12 bytes for GCM)
        if len(nonce) != self.NONCE_SIZE:
            raise ValueError(f"Nonce must be exactly {self.NONCE_SIZE} bytes long, but got {len(nonce)}")

        # Validate tag length (must be 16 bytes for GCM)
        if len(tag) != self.TAG_SIZE:
            raise ValueError(f"Authentication tag must be exactly {self.TAG_SIZE} bytes long")

        # Validate ciphertext is not empty
        if len(ciphertext) == 0:
            raise ValueError("Ciphertext cannot be empty")

        # Reattach tag to ciphertext for AESGCM.decrypt
        ct_and_tag = ciphertext + tag
        plaintext = self.aesgcm.decrypt(nonce, ct_and_tag, associated_data)
        return plaintext
