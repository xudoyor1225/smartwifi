"""Crypto service for AES-256-GCM encryption of router passwords.

Provides encrypt/decrypt functions using AES-256-GCM with random IVs.
The encryption key is sourced from application settings.

Requirements: 9.4
"""

import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings


def _get_key() -> bytes:
    """Get the 32-byte encryption key from settings.

    Returns:
        The encryption key as bytes (must be exactly 32 bytes for AES-256).
    """
    settings = get_settings()
    key = settings.encryption_key.encode("utf-8")
    if len(key) != 32:
        raise ValueError(
            f"Encryption key must be exactly 32 bytes, got {len(key)} bytes"
        )
    return key


def encrypt_password(plaintext: str) -> tuple[bytes, bytes]:
    """Encrypt a password using AES-256-GCM.

    Args:
        plaintext: The password string to encrypt.

    Returns:
        A tuple of (ciphertext_bytes, iv_bytes).
        The ciphertext includes the GCM authentication tag.
    """
    key = _get_key()
    iv = os.urandom(12)  # 96-bit IV recommended for GCM
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(iv, plaintext.encode("utf-8"), None)
    return ciphertext, iv


def decrypt_password(ciphertext: bytes, iv: bytes) -> str:
    """Decrypt a password encrypted with AES-256-GCM.

    Args:
        ciphertext: The encrypted password bytes (includes GCM auth tag).
        iv: The initialization vector used during encryption.

    Returns:
        The decrypted password string.

    Raises:
        cryptography.exceptions.InvalidTag: If the ciphertext has been tampered with.
    """
    key = _get_key()
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(iv, ciphertext, None)
    return plaintext.decode("utf-8")
