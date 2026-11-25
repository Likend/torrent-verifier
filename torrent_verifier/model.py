from __future__ import annotations

from bisect import bisect_right
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TorrentFile:
    path: list[str]
    length: int
    index: int

    @classmethod
    def from_bencode(cls, value: Any, index: int) -> TorrentFile:  # pyright: ignore[reportExplicitAny, reportAny]
        file = _mapping(value)
        path_key = b"path" if b"path" in file else b"path.utf-8"
        path = file[path_key]  # pyright: ignore[reportAny]
        if isinstance(path, bytes):
            parts = [_text(path)]
        elif isinstance(path, Sequence):
            parts = [_text(part) for part in path]
        else:
            raise TypeError("file path must be a sequence")
        if not parts:
            raise ValueError("file path must not be empty")
        return cls(parts, _non_negative_int(file[b"length"]), index)

    @property
    def display_path(self) -> str:
        return "/".join(self.path)


@dataclass
class TorrentMetadata:
    name: str
    piece_length: int
    piece_hashes: list[bytes]
    files: list[TorrentFile]

    @classmethod
    def from_bencode(cls, decoded: Mapping[bytes, Any]) -> TorrentMetadata:  # pyright: ignore[reportExplicitAny]
        """Build domain metadata from ``bencodepy.decode`` output."""
        info = _mapping(decoded[b"info"])
        name = _text(info[b"name"])
        piece_length = _non_negative_int(info[b"piece length"])
        pieces = _bytes(info[b"pieces"])
        if len(pieces) % 20:
            raise ValueError("pieces must contain complete SHA-1 hashes")

        if b"files" in info:
            files = [
                TorrentFile.from_bencode(item, i)
                for i, item in enumerate(_sequence(info[b"files"]))  # pyright: ignore[reportAny]
            ]
        else:
            length = _non_negative_int(info[b"length"])
            files = [TorrentFile([name], length, 0)]

        return cls(
            name=name,
            piece_length=piece_length,
            piece_hashes=[pieces[i : i + 20] for i in range(0, len(pieces), 20)],
            files=files,
        )

    @property
    def total_length(self) -> int:
        return sum(file.length for file in self.files)

    @dataclass
    class IndexCache:
        index: list[
            int
        ]  # 每个文件的起始偏移，以及最后一位是所有文件总大小。元素单调递增

        @property
        def total_size(self) -> int:
            return self.index[-1]

        def find_offset(self, offset: int) -> int:
            """根据 offset 查找属于第几个文件
            require offset >= 0 = index[0]
            return max(i) where index[i] <= offset
            """
            assert self.index[0] <= offset
            return bisect_right(self.index, offset) - 1

    def _index_cache(self) -> IndexCache:
        try:
            cache = self._cached_index
        except AttributeError:
            position = 0
            index = [0]
            for file in self.files:
                end = position + file.length
                index.append(end)
                position = end

            cache = self.IndexCache(index)
            self._cached_index = cache  # pyright: ignore[reportUninitializedInstanceVariable]
        return cache

    def iter_file_ranges(self) -> Iterator[tuple[TorrentFile, int, int]]:
        cache = self._index_cache().index
        for i, file in enumerate(self.files):
            yield file, cache[i], cache[i + 1]

    def get_file_range(self, file: TorrentFile) -> tuple[int, int]:
        cache = self._index_cache().index
        index = file.index
        return cache[index], cache[index + 1]

    def list_file_in_range(
        self, start: int, end: int
    ) -> Iterator[tuple[TorrentFile, int, int]]:
        cache = self._index_cache()
        start_index = cache.find_offset(start)
        end_index = cache.find_offset(end)
        if end == cache.index[end_index]:
            end_index -= 1
        for i in range(start_index, end_index + 1):
            if cache.index[i] != cache.index[i + 1]:
                yield self.files[i], cache.index[i], cache.index[i + 1]


def _mapping(value: Any) -> Mapping[bytes, Any]:  # pyright: ignore[reportAny, reportExplicitAny]
    if not isinstance(value, Mapping):
        raise TypeError("expected a mapping")
    return value  # pyright: ignore[reportUnknownVariableType]


def _sequence(value: Any) -> Sequence[Any]:  # pyright: ignore[reportAny, reportExplicitAny]
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise TypeError("expected a sequence")
    return value


def _text(value: Any) -> str:  # pyright: ignore[reportAny, reportExplicitAny]
    if isinstance(value, bytes):
        return value.decode("utf-8")
    raise TypeError("expected bytes containing UTF-8 text")


def _bytes(value: Any) -> bytes:  # pyright: ignore[reportAny, reportExplicitAny]
    if isinstance(value, bytes):
        return value
    raise TypeError("expected bytes")


def _non_negative_int(value: Any) -> int:  # pyright: ignore[reportAny, reportExplicitAny]
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("expected a non-negative integer")
    return value
