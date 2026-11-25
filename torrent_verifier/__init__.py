"""Torrent piece verification with an injectable filesystem."""

from os import PathLike
from pathlib import Path

import bencodepy

from .filesystem import FileSystem, LocalFileSystem
from .model import TorrentFile, TorrentMetadata
from .verifier import FileVerification, TorrentVerifier, VerificationReport


def load_torrent(path: str | PathLike[str]) -> TorrentMetadata:
    with Path(path).open("rb") as stream:
        return TorrentMetadata.from_bencode(bencodepy.decode(stream.read()))


__all__ = [
    "FileSystem",
    "FileVerification",
    "LocalFileSystem",
    "TorrentFile",
    "TorrentMetadata",
    "TorrentVerifier",
    "VerificationReport",
    "load_torrent",
]
