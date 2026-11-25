from argparse import ArgumentParser
from pathlib import Path

from tqdm import tqdm

from torrent_verifier import (
    LocalFileSystem,
    TorrentMetadata,
    TorrentVerifier,
    VerificationReport,
    load_torrent,
)
from torrent_verifier.verifier import Detail, ErrorDetail, ProgressDetail


def invoke(metadata: TorrentMetadata, fs: LocalFileSystem):
    verifier = TorrentVerifier(metadata, fs)

    pbar = tqdm(total=len(metadata.piece_hashes))

    def log_handler(detail: Detail):
        if isinstance(detail, ProgressDetail):
            pbar.update(detail.cur - pbar.n)
        elif isinstance(detail, ErrorDetail):
            pbar.write(str(detail))

    report = verifier.verify(log_handler)
    pbar.close()

    print_report(metadata, report)


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
    args = parser.parse_args()

    metadata = load_torrent(args.input)
    fs = LocalFileSystem(args.content)
    for torrent_path, mount_to in args.mount:
        path = torrent_path.split("/")
        if not torrent_path or any(not component for component in path):
            parser.error(
                "--mount torrent path must contain non-empty components separated by '/'"
            )
        fs.mount(path, Path(mount_to))

    invoke(metadata, fs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
