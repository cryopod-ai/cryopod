"""Tests for the cryopod crypto module."""

import click
import pytest

from cryopod.crypto import (
    decrypt_archive,
    encrypt_archive,
    is_encrypted,
)


class TestEncryptDecryptRoundtrip:
    """Tests for encrypt/decrypt roundtrip."""

    def test_roundtrip(self):
        """Encrypt then decrypt returns original bytes."""
        original = b"hello world this is test data"
        secret = "my-secret-key"
        encrypted = encrypt_archive(original, secret)
        decrypted = decrypt_archive(encrypted, secret)
        assert decrypted == original

    def test_roundtrip_empty(self):
        """Encrypt then decrypt works on empty bytes."""
        original = b""
        secret = "my-secret-key"
        encrypted = encrypt_archive(original, secret)
        decrypted = decrypt_archive(encrypted, secret)
        assert decrypted == original

    def test_roundtrip_large(self):
        """Encrypt then decrypt works on larger data."""
        original = b"x" * 100_000
        secret = "my-secret-key"
        encrypted = encrypt_archive(original, secret)
        decrypted = decrypt_archive(encrypted, secret)
        assert decrypted == original


class TestIsEncrypted:
    """Tests for is_encrypted detection."""

    def test_encrypted_data(self):
        """Encrypted data is detected as encrypted."""
        encrypted = encrypt_archive(b"test data", "secret")
        assert is_encrypted(encrypted) is True

    def test_plain_data(self):
        """Plain data is not detected as encrypted."""
        assert is_encrypted(b"\x1f\x8b some gzip data") is False

    def test_empty_data(self):
        """Empty data is not detected as encrypted."""
        assert is_encrypted(b"") is False

    def test_partial_magic(self):
        """Partial magic header is not detected as encrypted."""
        assert is_encrypted(b"CRYOPOD") is False


class TestDecryptionErrors:
    """Tests for decryption error handling."""

    def test_wrong_key(self):
        """Decrypt with wrong key raises ClickException."""
        encrypted = encrypt_archive(b"sensitive data", "key-a")
        with pytest.raises(click.ClickException, match="Decryption failed"):
            decrypt_archive(encrypted, "key-b")

    def test_truncated_data(self):
        """Truncated data raises ClickException."""
        with pytest.raises(click.ClickException, match="too short"):
            decrypt_archive(b"short", "secret")

    def test_bad_magic(self):
        """Data with wrong magic raises ClickException."""
        bad_data = b"NOT_CRYOPOD_" + b"\x01" + b"\x00" * 16 + b"token"
        with pytest.raises(click.ClickException, match="Not a valid"):
            decrypt_archive(bad_data, "secret")

    def test_bad_version(self):
        """Data with unsupported version raises ClickException."""
        bad_data = b"CRYOPOD_ENC" + b"\x99" + b"\x00" * 16 + b"token"
        with pytest.raises(
            click.ClickException, match="Unsupported encryption version"
        ):
            decrypt_archive(bad_data, "secret")
