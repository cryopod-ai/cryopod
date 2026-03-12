"""Shared encryption/decryption primitives and utilities for Cryopod CLI."""

import base64
import os

import click
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

MAGIC = b"CRYOPOD_ENC"
VERSION = b"\x01"
SALT_LEN = 16
HEADER_LEN = len(MAGIC) + len(VERSION) + SALT_LEN  # 11 + 1 + 16 = 28
PBKDF2_ITERATIONS = 600_000


def derive_fernet_key(secret_key: str, salt: bytes) -> bytes:
    """Derive a Fernet key from a secret string and salt using PBKDF2."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    derived = kdf.derive(secret_key.encode())
    return base64.urlsafe_b64encode(derived)


def encrypt_archive(archive: bytes, secret_key: str) -> bytes:
    """Encrypt archive bytes with a secret key using Fernet.

    Output format:
        11 bytes: magic 'CRYOPOD_ENC' (ASCII)
        1 byte:   version 0x01
        16 bytes: random salt
        remaining: Fernet token
    """
    salt = os.urandom(SALT_LEN)
    fernet_key = derive_fernet_key(secret_key, salt)
    token = Fernet(fernet_key).encrypt(archive)
    return MAGIC + VERSION + salt + token


def decrypt_archive(encrypted: bytes, secret_key: str) -> bytes:
    """Decrypt an encrypted archive produced by encrypt_archive.

    Raises click.ClickException on any decryption failure.
    """
    if len(encrypted) < HEADER_LEN:
        raise click.ClickException("Encrypted archive is too short to be valid.")

    magic = encrypted[: len(MAGIC)]
    version = encrypted[len(MAGIC) : len(MAGIC) + len(VERSION)]
    salt = encrypted[len(MAGIC) + len(VERSION) : HEADER_LEN]
    token = encrypted[HEADER_LEN:]

    if magic != MAGIC:
        raise click.ClickException("Not a valid encrypted Cryopod archive.")

    if version != VERSION:
        raise click.ClickException(f"Unsupported encryption version: {version!r}.")

    fernet_key = derive_fernet_key(secret_key, salt)
    try:
        return Fernet(fernet_key).decrypt(token)
    except InvalidToken as err:
        raise click.ClickException(
            "Decryption failed. Wrong key or corrupted archive."
        ) from err


def is_encrypted(data: bytes) -> bool:
    """Check if bytes start with the CRYOPOD_ENC magic header."""
    return data[: len(MAGIC)] == MAGIC
