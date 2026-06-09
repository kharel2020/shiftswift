"""AES-256-GCM encryption for sensitive grievance case notes."""

from __future__ import annotations

import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _encryption_key() -> bytes:
    raw = os.getenv("ENCRYPTION_KEY", "")
    if not raw:
        raise ValueError("ENCRYPTION_KEY is not configured (64 hex chars = 32 bytes)")
    key = bytes.fromhex(raw)
    if len(key) != 32:
        raise ValueError("ENCRYPTION_KEY must be 32 bytes (64 hex characters)")
    return key


def encrypt_text(text: str) -> str:
    key = _encryption_key()
    iv = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(iv, text.encode("utf-8"), None)
    return f"{iv.hex()}:{ciphertext.hex()}"


def decrypt_text(encrypted_blob: str) -> str:
    key = _encryption_key()
    iv_hex, ciphertext_hex = encrypted_blob.split(":", 1)
    iv = bytes.fromhex(iv_hex)
    ciphertext = bytes.fromhex(ciphertext_hex)
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(iv, ciphertext, None).decode("utf-8")


def encryption_configured() -> bool:
    raw = os.getenv("ENCRYPTION_KEY", "")
    try:
        return len(bytes.fromhex(raw)) == 32 if raw else False
    except ValueError:
        return False
