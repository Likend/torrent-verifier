from __future__ import annotations

import hashlib
from collections.abc import Callable, Set
from contextlib import ExitStack
from dataclasses import dataclass, field
from typing import BinaryIO, override

from sortedcontainers.sortedset import SortedSet

from .filesystem import FileSystem
from .model import TorrentFile, TorrentMetadata


class Detail:
    pass


class ErrorDetail(Detail):
    pass


@dataclass(frozen=True)
class ProgressDetail(Detail):
    cur: int
    total: int

    @override
    def __str__(self) -> str:
        return f"Progress {self.cur}/{self.total}"


@dataclass(frozen=True)
class BlockErrorDetail(ErrorDetail):
    index: int

    @override
    def __str__(self) -> str:
        return f"Block #{self.index} damaged"


@dataclass(frozen=True)
class FileErrorDetail(ErrorDetail):
    file: TorrentFile


@dataclass(frozen=True)
class FileLengthErrorDetail(FileErrorDetail):
    actual_length: int

    @override
    def __str__(self) -> str:
        return f"Actual length of file {self.file.display_path} is {self.actual_length}, expected {self.file.length}"


@dataclass(frozen=True)
class FileOSErrorDetail(FileErrorDetail):
    exc: OSError

    @override
    def __str__(self) -> str:
        return f"OSError occurred when verifying {self.file.display_path}: {self.exc}"


@dataclass
class FileVerification:
    start: int
    end: int
    length: int
    verified: bool
    error: list[ErrorDetail] = field(default_factory=list)


class VerificationReport:
    def __init__(self, metadata: TorrentMetadata) -> None:
        self.metadata = metadata
        self._files: list[FileVerification] = [
            FileVerification(start=start, end=end, length=file.length, verified=True)
            for file, start, end in metadata.iter_file_ranges()
        ]
        self.verified_blocks: SortedSet[int] = SortedSet()

    def get(self, file: TorrentFile) -> FileVerification | None:
        if file.index in range(len(self._files)):
            return self[file]

    def __getitem__(self, file: TorrentFile) -> FileVerification:
        return self._files[file.index]

    def _add_block_verification(
        self,
        block_index: int,
        start: int,
        end: int,
        verified: bool,
        log_handler: Callable[[Detail], None] = lambda _: None,
    ):
        if verified:
            self.verified_blocks.add(block_index)
        else:
            for file, _, _ in self.metadata.list_file_in_range(start, end):
                current_report = self[file]
                current_report.verified = False
                detail = BlockErrorDetail(block_index)
                current_report.error.append(detail)
                log_handler(detail)

    @property
    def verified(self) -> bool:
        return self.pieces_failed == 0 and all(file.verified for file in self._files)

    @property
    def pieces_verified(self) -> int:
        return len(self.verified_blocks)

    @property
    def pieces_failed(self) -> int:
        return self.block_number - self.pieces_verified

    @property
    def block_number(self) -> int:
        return self.metadata.block_number

    @override
    def __repr__(self) -> str:
        return f"VerificationReport(verified={self.verified}, pieces_verified={self.pieces_verified}, pieces_failed={self.pieces_failed}, files={self._files})"


class TorrentVerifier:
    def __init__(
        self,
        metadata: TorrentMetadata,
        filesystem: FileSystem,
        mask: Set[int] | None = None,
    ):
        self.metadata = metadata
        self.filesystem = filesystem
        self.mask = mask or set()
        """Store verified block numbers"""

    def verify(
        self, log_handler: Callable[[Detail], None] = lambda _: None
    ) -> VerificationReport:
        report = VerificationReport(self.metadata)
        report.verified_blocks |= self.mask

        def report_error(detail: FileErrorDetail):
            current_report = report[detail.file]
            current_report.verified = False
            current_report.error.append(detail)
            log_handler(detail)

        with ExitStack() as stack:
            file_ios: list[BinaryIO | None] = []
            for file in self.metadata.files:
                try:
                    stream = stack.enter_context(self.filesystem.open(file.path))
                    actual_length = _stream_length(stream)
                    if actual_length != file.length:
                        report_error(
                            FileLengthErrorDetail(
                                file=file, actual_length=actual_length
                            ),
                        )
                    file_ios.append(stream)
                except OSError as exc:
                    report_error(FileOSErrorDetail(file=file, exc=exc))
                    file_ios.append(None)

            total = self.metadata.block_number - len(self.mask)

            count = 0
            for index, expected in enumerate(self.metadata.piece_hashes):
                log_handler(ProgressDetail(cur=count, total=total))
                if index in self.mask:
                    continue
                start = index * self.metadata.piece_length
                size = min(
                    self.metadata.piece_length, self.metadata.total_length - start
                )
                verified = (
                    hashlib.sha1(self._read_range(file_ios, start, size)).digest()
                    == expected
                )
                report._add_block_verification(  # pyright: ignore[reportPrivateUsage]
                    index, start, start + size, verified, log_handler
                )
                count += 1

        return report

    def _read_range(
        self, file_ios: list[BinaryIO | None], start: int, size: int
    ) -> bytes:
        if size <= 0:
            return b""

        result = bytearray()
        for (_, file_start, file_end), stream in zip(
            self.metadata.iter_file_ranges(), file_ios
        ):
            overlap_start = max(start, file_start)
            overlap_end = min(start + size, file_end)
            if overlap_start >= overlap_end or stream is None:
                continue

            stream.seek(overlap_start - file_start)
            result.extend(stream.read(overlap_end - overlap_start))
        return bytes(result)


def _stream_length(stream: BinaryIO):
    stream.seek(0, 2)
    length = stream.tell()
    stream.seek(0)
    return length
