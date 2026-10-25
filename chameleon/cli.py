"""The ``chameleon-cli`` command: the same conversion without a window, for scripts and terminals.

    chameleon-cli                      convert the HEIC photos in the current folder
    chameleon-cli Photos -r -o JPEG    convert a folder and its subfolders into another folder
"""

from __future__ import annotations

import argparse
import sys
import threading

from chameleon import __app_name__, __version__
from chameleon.core import MAX_WORKERS, ConversionJob, ConvertOptions, ExistingFiles, OutputFormat, Phase
from chameleon.utils.formatting import format_bytes, format_duration

POLL_SECONDS = 0.5
# Output stays plain ASCII: Windows consoles and redirected output often use a code page without "→" or "…".


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="chameleon-cli",
        description="Convert HEIC photos (the iPhone's format) to JPEG or PNG, keeping their date, colours "
                    "and details. Originals are never changed.",
    )
    parser.add_argument("paths", nargs="*", default=["."], metavar="PATH",
                        help="photos or folders to convert (default: the current folder)")
    parser.add_argument("-r", "--recursive", action="store_true", help="also convert photos in subfolders")
    parser.add_argument("-o", "--output", metavar="FOLDER",
                        help="save the converted photos here, keeping the folder structure "
                             "(default: next to each original)")
    parser.add_argument("--png", action="store_true", help="save PNG instead of JPEG (lossless, larger files)")
    parser.add_argument("-q", "--quality", type=int, default=90, metavar="1-100",
                        help="JPEG quality (default: 90)")
    parser.add_argument("--no-metadata", action="store_true",
                        help="don't keep the date taken, camera details and colour profile")
    parser.add_argument("--remove-location", action="store_true", help="remove GPS coordinates from the photos")
    parser.add_argument("--existing", choices=[choice.value for choice in ExistingFiles], default="skip",
                        help="when the converted name is taken: skip the photo, replace the file, "
                             "or keep both by numbering the new one (default: skip)")
    parser.add_argument("-j", "--workers", type=int, metavar="N",
                        help=f"photos converted at the same time (1-{MAX_WORKERS}, default: one per processor core)")
    parser.add_argument("--version", action="version", version=f"{__app_name__} {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not 1 <= args.quality <= 100:
        print("error: --quality must be between 1 and 100", file=sys.stderr)
        return 2
    options = ConvertOptions(
        output_format=OutputFormat.PNG if args.png else OutputFormat.JPEG,
        quality=args.quality,
        keep_metadata=not args.no_metadata,
        remove_location=args.remove_location,
        destination=args.output,
        include_subfolders=args.recursive,
        existing=ExistingFiles(args.existing),
    )
    try:
        job = ConversionJob(args.paths, options, workers=args.workers)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    thread = threading.Thread(target=job.run, name="chameleon-job", daemon=True)
    thread.start()
    interactive = sys.stdout.isatty()
    try:
        while thread.is_alive():
            thread.join(POLL_SECONDS)
            if interactive:
                _print_progress(job)
    except KeyboardInterrupt:
        print("\nStopping after the photos being converted...", file=sys.stderr)
        job.cancel()
        thread.join()
    if interactive:
        print()

    result = job.result
    assert result is not None
    if result.photos_found == 0:
        print("No HEIC photos found in: " + ", ".join(job.sources))
        return 0
    print(f"Converted {result.converted:,} of {result.photos_found:,} photos "
          f"({format_bytes(result.bytes_in)} -> {format_bytes(result.bytes_out)}) in {format_duration(result.elapsed)}.")
    if result.skipped_existing:
        print(f"Skipped {result.skipped_existing:,} photo(s) whose converted file already exists "
              "(use --existing replace or keep-both).")
    for error in result.errors:
        print(f"Failed: {error.path}: {error.message}", file=sys.stderr)
    if result.cancelled:
        return 130
    return 1 if result.errors else 0


def _print_progress(job: ConversionJob) -> None:
    snap = job.snapshot()
    if snap.phase is Phase.SCANNING:
        line = f"Looking for photos... {snap.files_done:,} found"
    elif snap.phase is Phase.CONVERTING:
        line = f"Converting {snap.files_done:,} of {snap.files_total:,} ({snap.fraction:.0%})"
        if snap.eta is not None:
            line += f", about {format_duration(snap.eta)} left"
    else:
        return
    print(f"\r{line:<70}", end="", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
