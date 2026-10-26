"""Content-addressed storage for cleaned media. Local disk by default.

Keys are sha256 of cleaned bytes, never user-supplied names, so there is no path traversal
surface. Swap LocalStore for an S3/R2 implementation in production.
"""
import hashlib
import os
import re

from app.core.config import get_settings

_KEY_RE = re.compile(r"^[a-f0-9]{64}\.jpg$")


class LocalStore:
    def __init__(self, root: str):
        self.root = os.path.abspath(root)
        os.makedirs(self.root, exist_ok=True)

    def put_jpeg(self, data: bytes) -> str:
        key = hashlib.sha256(data).hexdigest() + ".jpg"
        path = os.path.join(self.root, key)
        if not os.path.exists(path):
            tmp = path + ".tmp"
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, path)
        return key

    def path(self, key: str) -> str | None:
        if not _KEY_RE.match(key):
            return None
        p = os.path.join(self.root, key)
        return p if os.path.isfile(p) else None

    def get(self, key: str) -> bytes | None:
        p = self.path(key)
        if not p:
            return None
        with open(p, "rb") as f:
            return f.read()


_store: LocalStore | None = None


def store() -> LocalStore:
    global _store
    if _store is None:
        _store = LocalStore(get_settings().upload_dir)
    return _store
