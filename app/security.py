from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


class CredentialError(Exception):
    pass


class SecretBox:
    """Encrypt mailbox authorization codes with a key kept on this machine."""

    def __init__(self, key_path: Path, env_key: str | None = None) -> None:
        self._fernet = Fernet(self._resolve_key(key_path, env_key))

    @staticmethod
    def _resolve_key(key_path: Path, env_key: str | None) -> bytes:
        if env_key:
            return base64.urlsafe_b64encode(hashlib.sha256(env_key.encode("utf-8")).digest())

        if key_path.exists():
            key = key_path.read_bytes().strip()
            try:
                Fernet(key)
            except (ValueError, TypeError) as exc:
                raise RuntimeError(f"本地密钥文件损坏：{key_path}") from exc
            return key

        key_path.parent.mkdir(parents=True, exist_ok=True)
        key = Fernet.generate_key()
        key_path.write_bytes(key)
        try:
            os.chmod(key_path, 0o600)
        except OSError:
            pass
        return key

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode("utf-8")).decode("ascii")

    def decrypt(self, token: str) -> str:
        try:
            return self._fernet.decrypt(token.encode("ascii")).decode("utf-8")
        except (InvalidToken, ValueError) as exc:
            raise CredentialError(
                "无法解密已保存的授权码。本地密钥可能已丢失，请重新输入授权码。"
            ) from exc
