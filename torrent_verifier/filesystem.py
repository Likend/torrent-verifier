from __future__ import annotations

import os
from collections.abc import Generator, Sequence
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path
from typing import BinaryIO, Protocol

from sortedcontainers import SortedDict


class FileSystem(Protocol):
    def open(self, path: Sequence[str]) -> AbstractContextManager[BinaryIO]: ...


class LocalFileSystem:
    def __init__(self, root: str | os.PathLike[str] = ".") -> None:
        root = Path(root)
        self._mount_map: SortedDict[tuple[str, ...], Path] = SortedDict({(): root})

    @contextmanager
    def open(self, path: Sequence[str]) -> Generator[BinaryIO]:
        def search_real_path(path: Sequence[str]) -> Path:
            for i in range(len(path), -1, -1):
                mount_root = self._mount_map.get(tuple(path[:i]))
                if mount_root is not None:
                    return mount_root.joinpath(*path[i:])
            raise AssertionError("unreachable")

        real_path = search_real_path(path)

        with (real_path).open("rb") as file:
            yield file

    def mount(self, path: Sequence[str], to: str | os.PathLike[str]):
        self._mount_map[tuple(path)] = Path(to)

    def unmount(self, path: Sequence[str]):
        if len(path) == 1:
            raise ValueError("Can not unmount root path")
        del self._mount_map[tuple(path)]

    def __repr__(self) -> str:
        kv = (
            f'"{"/".join(key) if len(key) else "."}":"{value}"'
            for key, value in self._mount_map.items()
        )
        return f"LocalFileSystem(mount={', '.join(kv)})"
