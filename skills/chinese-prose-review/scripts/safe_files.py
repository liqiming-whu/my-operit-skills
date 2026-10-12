"""Byte-preserving input and exclusive output; Python standard library only."""
from hashlib import sha256
from pathlib import Path


def read_source(path):
    data = path.read_bytes()
    return data.decode("utf-8"), sha256(data).hexdigest()


def write_new(path, content):
    # x mode rejects existing files, symlinks and hard links without truncation.
    path = path.expanduser().absolute()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="") as stream:
        stream.write(content)
