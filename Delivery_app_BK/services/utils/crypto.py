import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken


def _build_fernet() -> Fernet:
    secret = (
        os.getenv("APP_SECRET_KEY")
        or os.getenv("SECRET_KEY")
        or os.getenv("JWT_SECRET_KEY")
    )
    if not isinstance(secret, str) or not secret.strip():
        raise RuntimeError("Encryption key is not configured.")

    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    fernet_key = base64.urlsafe_b64encode(digest)
    return Fernet(fernet_key)


def encrypt_secret(plain_text: str) -> str:
    if not isinstance(plain_text, str) or not plain_text:
        raise ValueError("Secret must be a non-empty string.")
    return _build_fernet().encrypt(plain_text.encode("utf-8")).decode("utf-8")


def decrypt_secret(cipher_text: str) -> str:
    if not isinstance(cipher_text, str) or not cipher_text:
        raise ValueError("Cipher text must be a non-empty string.")
    try:
        return _build_fernet().decrypt(cipher_text.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Invalid encrypted secret.") from exc
