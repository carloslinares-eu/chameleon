"""Plain data types passed between the engine, the user interface and the command line."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field


class Phase(enum.Enum):
    """The steps a job goes through, in order."""

    IDLE = "idle"
    SCANNING = "scanning"  # finding the HEIC photos in the chosen files and folders
    CONVERTING = "converting"  # converting each photo
    FINISHED = "finished"


class OutputFormat(enum.Enum):
    JPEG = "jpeg"
    PNG = "png"

    @property
    def extension(self) -> str:
        return ".jpg" if self is OutputFormat.JPEG else ".png"

    @property
    def pillow_name(self) -> str:
        return self.name


class ExistingFiles(enum.Enum):
    """What to do when a converted photo's name is already taken."""

    SKIP = "skip"  # leave the existing file alone and don't convert that photo
    REPLACE = "replace"  # overwrite it
    KEEP_BOTH = "keep-both"  # save the new one as "name (2).jpg"


@dataclass(frozen=True, slots=True)
class ConvertOptions:
    output_format: OutputFormat = OutputFormat.JPEG
    quality: int = 90  # JPEG only, 1-100
    keep_metadata: bool = True  # date taken, camera details, colour profile (EXIF, ICC, XMP)
    remove_location: bool = False  # drop GPS coordinates even when keeping the rest
    destination: str | None = None  # None: next to each original
    include_subfolders: bool = True
    existing: ExistingFiles = ExistingFiles.SKIP


@dataclass(frozen=True, slots=True)
class FoundPhoto:
    """A HEIC photo found while scanning."""

    source: str
    relative: str  # path below the folder it was found in (just the name for photos added one by one)
    size: int


@dataclass(frozen=True, slots=True)
class PhotoTask:
    """A photo that will be converted, and where the result goes."""

    index: int  # order found; results are reported in this order
    source: str
    target: str
    size: int


@dataclass(frozen=True, slots=True)
class FileError:
    """A photo or folder that could not be processed."""

    path: str
    message: str
    phase: Phase


@dataclass(frozen=True, slots=True)
class ProgressSnapshot:
    """A consistent view of the job's progress, safe to read from the GUI thread."""

    phase: Phase
    files_done: int
    files_total: int
    bytes_done: int
    bytes_total: int
    elapsed: float  # seconds since the job started
    rate: float | None  # photos per second over the last few seconds
    eta: float | None  # seconds left in the current phase
    current_file: str | None

    @property
    def fraction(self) -> float:
        """Completed share of the current phase, from 0.0 to 1.0."""
        if self.bytes_total > 0:
            done, total = self.bytes_done, self.bytes_total
        elif self.files_total > 0:
            done, total = self.files_done, self.files_total
        else:
            return 1.0 if self.phase is Phase.FINISHED else 0.0
        return max(0.0, min(1.0, done / total))


@dataclass(slots=True)
class JobResult:
    photos_found: int = 0
    converted: int = 0
    skipped_existing: int = 0  # name already taken and ExistingFiles.SKIP
    bytes_in: int = 0  # size of the HEIC photos that were converted
    bytes_out: int = 0  # size of what was written
    elapsed: float = 0.0
    cancelled: bool = False
    errors: list[FileError] = field(default_factory=list)
    output_folders: list[str] = field(default_factory=list)  # where converted photos went, first one first
