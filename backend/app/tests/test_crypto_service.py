"""Tests for the crypto service (AES-256-GCM encryption/decryption)."""

import pytest
from unittest.mock import patch

from app.services.crypto_service import decrypt_password, encrypt_password


class TestEncryptPassword:
    """Tests for encrypt_password function."""

    @patch("app.services.crypto_service.get_settings")
    def test_encrypt_returns_ciphertext_and_iv(self, mock_settings):
        """Encrypt should return a tuple of (ciphertext, iv)."""
        mock_settings.return_value.encryption_key = "a" * 32
        ciphertext, iv = encrypt_password("my_secret_password")
        assert isinstance(ciphertext, bytes)
        assert isinstance(iv, bytes)
        assert len(iv) == 12  # 96-bit IV for GCM

    @patch("app.services.crypto_service.get_settings")
    def test_encrypt_produces_different_ciphertext_each_time(self, mock_settings):
        """Each encryption should produce different ciphertext due to random IV."""
        mock_settings.return_value.encryption_key = "a" * 32
        ct1, iv1 = encrypt_password("same_password")
        ct2, iv2 = encrypt_password("same_password")
        # IVs should differ (random)
        assert iv1 != iv2
        # Ciphertext should differ due to different IVs
        assert ct1 != ct2

    @patch("app.services.crypto_service.get_settings")
    def test_encrypt_ciphertext_not_plaintext(self, mock_settings):
        """Ciphertext should not contain the plaintext."""
        mock_settings.return_value.encryption_key = "b" * 32
        plaintext = "visible_password"
        ciphertext, _ = encrypt_password(plaintext)
        assert plaintext.encode("utf-8") not in ciphertext


class TestDecryptPassword:
    """Tests for decrypt_password function."""

    @patch("app.services.crypto_service.get_settings")
    def test_decrypt_recovers_original_password(self, mock_settings):
        """Decrypt should recover the original plaintext password."""
        mock_settings.return_value.encryption_key = "c" * 32
        original = "super_secret_123!"
        ciphertext, iv = encrypt_password(original)
        decrypted = decrypt_password(ciphertext, iv)
        assert decrypted == original

    @patch("app.services.crypto_service.get_settings")
    def test_decrypt_with_wrong_iv_fails(self, mock_settings):
        """Decrypt with wrong IV should raise an error."""
        mock_settings.return_value.encryption_key = "d" * 32
        ciphertext, _ = encrypt_password("password")
        wrong_iv = b"\x00" * 12
        with pytest.raises(Exception):
            decrypt_password(ciphertext, wrong_iv)

    @patch("app.services.crypto_service.get_settings")
    def test_decrypt_with_tampered_ciphertext_fails(self, mock_settings):
        """Decrypt with tampered ciphertext should raise an error (GCM auth)."""
        mock_settings.return_value.encryption_key = "e" * 32
        ciphertext, iv = encrypt_password("password")
        tampered = bytearray(ciphertext)
        tampered[0] ^= 0xFF  # Flip bits
        with pytest.raises(Exception):
            decrypt_password(bytes(tampered), iv)

    @patch("app.services.crypto_service.get_settings")
    def test_encrypt_decrypt_empty_string(self, mock_settings):
        """Should handle empty string encryption/decryption."""
        mock_settings.return_value.encryption_key = "f" * 32
        ciphertext, iv = encrypt_password("")
        decrypted = decrypt_password(ciphertext, iv)
        assert decrypted == ""

    @patch("app.services.crypto_service.get_settings")
    def test_encrypt_decrypt_unicode(self, mock_settings):
        """Should handle unicode characters in passwords."""
        mock_settings.return_value.encryption_key = "g" * 32
        original = "pässwörd_日本語"
        ciphertext, iv = encrypt_password(original)
        decrypted = decrypt_password(ciphertext, iv)
        assert decrypted == original


class TestKeyValidation:
    """Tests for encryption key validation."""

    @patch("app.services.crypto_service.get_settings")
    def test_invalid_key_length_raises_error(self, mock_settings):
        """Should raise ValueError if key is not 32 bytes."""
        mock_settings.return_value.encryption_key = "short_key"
        with pytest.raises(ValueError, match="must be exactly 32 bytes"):
            encrypt_password("password")
