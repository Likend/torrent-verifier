from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
from typing import cast

from sortedcontainers import SortedSet
from tqdm import tqdm

from torrent_verifier import (
    LocalFileSystem,
    TorrentMetadata,
    TorrentVerifier,
    VerificationReport,
    load_torrent,
)
from torrent_verifier.verifier import Detail, ErrorDetail, ProgressDetail


def prepare_mask(incre_cache: Path | None = None) -> SortedSet[int] | None:
    if incre_cache is None:
        return None
    mask: SortedSet[int] = SortedSet()
    if not incre_cache.exists():
        return mask
    with incre_cache.open("br") as file:
        i = 0
        while True:
            byte = file.read(1)
            if len(byte) == 0:
                break
            if byte == b"\x01":
                mask.add(i)
            i += 1
    return mask


def save_mask(report: VerificationReport, incre_cache: Path | None = None):
    if incre_cache is None:
        return
    with incre_cache.open("bw") as file:
        for i in range(report.block_number):
            if i in report.verified_blocks:
                file.write(b"\x01")
            else:
                file.write(b"\x00")


def invoke(
    metadata: TorrentMetadata, fs: LocalFileSystem, incre_cache: Path | None = None
):
    mask = prepare_mask(incre_cache)
    verifier = TorrentVerifier(metadata, fs, mask)

    pbar = tqdm()

    def log_handler(detail: Detail):
        if isinstance(detail, ProgressDetail):
            pbar.total = detail.total
            pbar.update(detail.cur - pbar.n)  # pyright: ignore[reportAny]
        elif isinstance(detail, ErrorDetail):
            pbar.write(str(detail))

    report = verifier.verify(log_handler)
    pbar.close()

    print_report(metadata, report)
    save_mask(report, incre_cache)


def print_report(metadata: TorrentMetadata, report: VerificationReport):
    print(f"Verification Report on Torrent `{metadata.name}`")
    if report.verified:
        print("Pass!")
    else:
        print("Failed!")
        print(f"verified pieces: {report.pieces_verified}")
        print(f"failed pieces: {report.pieces_failed}")

        for file in metadata.files:
            file_report = report[file]
            if not file_report.verified:
                print(f"Failed on `{file.display_path}`: ")

                for reason in file_report.error:
                    print(f"    {reason}")


def main():
    parser = ArgumentParser(description="Verify contents by a torrent file.")
    parser.add_argument("input", help="Input torrent path", type=Path)
    parser.add_argument(
        "content", help="Path to content file or root directory", type=Path
    )
    parser.add_argument(
        "--mount",
        "-m",
        action="append",
        nargs=2,
        metavar=("TORRENT_PATH", "MOUNT_TO_PATH"),
        default=[],
        help=(
            "Mount a torrent path (components separated by '/') to a local path; "
            "may be specified multiple times"
        ),
    )
    parser.add_argument(
        "--incre-cache",
        help="Path to increment cache to skip verrified blocks",
        type=Path,
    )
    args = parser.parse_args()
    input_path = cast(Path, args.input)
    content_path = cast(Path, args.content)
    mounts = cast(list[list[str]], args.mount)
    incre_cache = cast(Path | None, args.incre_cache)

    metadata = load_torrent(input_path)
    fs = LocalFileSystem(content_path)
    for torrent_path, mount_to in mounts:
        path = torrent_path.split("/")
        if not torrent_path or any(not component for component in path):
            parser.error(
                "--mount torrent path must contain non-empty components separated by '/'"
            )
        fs.mount(path, mount_to)

    invoke(metadata, fs, incre_cache)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
