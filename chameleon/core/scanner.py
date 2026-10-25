"""Finding HEIC photos in the files and folders the user chose."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable, Iterable, Iterator

from chameleon.core.models import FoundPhoto
from chameleon.utils.paths import StrPath

# .heic is what iPhones write; .heif and .hif are the same container from other cameras and apps.
HEIF_EXTENSIONS = frozenset({".heic", ".heif", ".hif"})
_IO_REPARSE_TAG_MOUNT_POINT = 0xA0000003  # a Windows junction


def is_heif(path: StrPath) -> bool:
    return os.path.splitext(os.fspath(path))[1].lower() in HEIF_EXTENSIONS


def find_photos(sources: Iterable[StrPath], include_subfolders: bool = True,
                on_error: Callable[[str, OSError], None] | None = None) -> Iterator[FoundPhoto]:
    """Every HEIC photo in ``sources``, in a stable order.

    A source can be a photo (yielded if it is a HEIC file) or a folder, searched
    alphabetically, its own photos before its subfolders. Shortcuts to other folders
    (symbolic links, junctions) aren't followed, so nothing is found twice.
    """
    for source in sources:
        source = os.path.abspath(source)
        if os.path.isdir(source):
            yield from _walk(source, include_subfolders, on_error)
        elif is_heif(source):
            try:
                yield FoundPhoto(source, os.path.basename(source), os.path.getsize(source))
            except OSError as exc:
                _report(on_error, source, exc)


def _walk(root: str, include_subfolders: bool, on_error: Callable[[str, OSError], None] | None,
          folder: str | None = None) -> Iterator[FoundPhoto]:
    folder = folder or root
    try:
        with os.scandir(folder) as scan:
            entries = sorted(scan, key=lambda entry: entry.name.lower())
    except OSError as exc:
        _report(on_error, folder, exc)
        return
    subfolders = []
    for entry in entries:
        try:
            if entry.is_dir(follow_symlinks=False):
                if not _is_link(entry):
                    subfolders.append(entry.path)
            elif entry.is_file() and is_heif(entry.name):
                yield FoundPhoto(entry.path, os.path.relpath(entry.path, root), entry.stat().st_size)
        except OSError as exc:
            _report(on_error, entry.path, exc)
    if include_subfolders:
        for subfolder in subfolders:
            yield from _walk(root, include_subfolders, on_error, subfolder)


def _is_link(entry: os.DirEntry) -> bool:
    """True for symlinks and Windows junctions, which are skipped to avoid loops."""
    if entry.is_symlink():
        return True
    if sys.version_info >= (3, 12):
        return entry.is_junction()
    reparse_tag = getattr(entry.stat(follow_symlinks=False), "st_reparse_tag", 0)
    return reparse_tag == _IO_REPARSE_TAG_MOUNT_POINT


def _report(on_error: Callable[[str, OSError], None] | None, path: str, exc: OSError) -> None:
    if on_error is not None:
        on_error(path, exc)
