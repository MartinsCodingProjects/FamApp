"""AES-256-GCM for secrets in the DB (README 9, BUILDPLAN 1.8).

Ciphertext format, version 1:

    0x01 | nonce (12 random bytes) | AES-GCM ciphertext + 16-byte tag

Associated data: b"famapp-secret:v1:" + secret name, so a ciphertext copied to another
secret's row does not decrypt. The version byte allows a later key rotation or algorithm.
"""

from __future__ import annotations

import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

VERSION = 1
NONCE_BYTES = 12
TAG_BYTES = 16
KEY_BYTES = 32


class DecryptionError(Exception):
    """Wrong key, tampered data, wrong secret name or unknown format. Never says which."""


def _aad(name: str) -> bytes:
    return b"famapp-secret:v1:" + name.encode("utf-8")


def _cipher(key: bytes) -> AESGCM:
    if len(key) != KEY_BYTES:
        raise ValueError("MASTER_KEY must be 32 bytes")
    return AESGCM(key)


def encrypt(key: bytes, name: str, plaintext: bytes) -> bytes:
    nonce = os.urandom(NONCE_BYTES)
    return bytes([VERSION]) + nonce + _cipher(key).encrypt(nonce, plaintext, _aad(name))


def decrypt(key: bytes, name: str, blob: bytes) -> bytes:
    if len(blob) < 1 + NONCE_BYTES + TAG_BYTES or blob[0] != VERSION:
        raise DecryptionError("cannot decrypt secret")
    nonce, body = blob[1 : 1 + NONCE_BYTES], blob[1 + NONCE_BYTES :]
    try:
        return _cipher(key).decrypt(nonce, body, _aad(name))
    except InvalidTag:
        raise DecryptionError("cannot decrypt secret") from None
