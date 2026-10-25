"""The job that converts a batch of photos, using a pool of worker threads.

A job runs in two phases:

1. **Scanning** - find every HEIC photo in the chosen files and folders, and work
   out where each converted photo goes and under which name. Names already taken
   are skipped, replaced or numbered, as the user chose; two photos of the same
   job never get the same name.
2. **Converting** - convert the photos in parallel. Each one is written under a
   temporary name and renamed when complete, so stopping never leaves a broken file.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections.abc import Callable, Iterable, Iterator, Sequence
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from typing import TypeVar

from chameleon.core.converter import convert_photo
from chameleon.core.errors import OperationCancelled
from chameleon.core.models import (
    ConvertOptions,
    ExistingFiles,
    FileError,
    FoundPhoto,
    JobResult,
    Phase,
    PhotoTask,
    ProgressSnapshot,
)
from chameleon.core.progress import ProgressTracker
from chameleon.core.scanner import find_photos
from chameleon.utils.paths import StrPath, path_key, unique_paths

log = logging.getLogger(__name__)

T = TypeVar("T")

MAX_WORKERS = 32


def default_workers() -> int:
    """Photo decoding is CPU-bound, so one thread per core (up to 8) keeps every core busy."""
    return max(1, min(8, os.cpu_count() or 4))


class ConversionJob:
    """Converts every HEIC photo in ``sources`` with ``options``.

    Call :meth:`run` from a background thread; it blocks until the job ends and
    returns a :class:`JobResult`. From any other thread, :meth:`snapshot` reports
    progress and :meth:`cancel` asks the job to stop: photos already being
    converted are finished, nothing new is started.
    """

    def __init__(self, sources: Iterable[StrPath], options: ConvertOptions, workers: int | None = None):
        self.sources = unique_paths(source for source in sources if source)
        if not self.sources:
            raise ValueError("Please add the photos or folders to convert.")
        for source in self.sources:
            if not os.path.exists(source):
                raise ValueError(f"This photo or folder doesn't exist anymore:\n{source}")
        if options.destination is not None:
            if not str(options.destination).strip():
                raise ValueError("Please choose the folder to save the converted photos in.")
            destination = os.path.abspath(options.destination)
            if os.path.exists(destination) and not os.path.isdir(destination):
                raise ValueError(f"The destination isn't a folder:\n{destination}")
        self.options = options
        self.workers = max(1, min(MAX_WORKERS, workers or default_workers()))

        self.result: JobResult | None = None
        self._cancel = threading.Event()
        self._tracker = ProgressTracker()
        self._errors: list[FileError] = []

    # -- control -------------------------------------------------------------

    def cancel(self) -> None:
        self._cancel.set()

    @property
    def cancel_requested(self) -> bool:
        return self._cancel.is_set()

    def snapshot(self) -> ProgressSnapshot:
        return self._tracker.snapshot()

    # -- running -------------------------------------------------------------

    def run(self) -> JobResult:
        result = JobResult()
        self._tracker.start_job()
        started = time.monotonic()
        try:
            found = self._scan()
            result.photos_found = len(found)
            tasks, result.skipped_existing = plan_tasks(found, self.options)
            result.output_folders = _folders_in_order(task.target for task in tasks)
            self._convert(tasks, result)
        except OperationCancelled:
            result.cancelled = True
        finally:
            result.elapsed = time.monotonic() - started
            result.errors = list(self._errors)
            self._tracker.finish()
            self.result = result
        return result

    def _scan(self) -> list[FoundPhoto]:
        found = []
        for photo in find_photos(self.sources, self.options.include_subfolders, self._scan_error):
            self._check_cancel()
            found.append(photo)
            self._tracker.set_current(photo.source)
            self._tracker.advance(files=1, nbytes=photo.size)
        return found

    def _convert(self, tasks: Sequence[PhotoTask], result: JobResult) -> None:
        self._tracker.begin_phase(Phase.CONVERTING, len(tasks), sum(task.size for task in tasks))
        for task, written, error in self._parallel(self._convert_one, tasks):
            if error is None:
                result.converted += 1
                result.bytes_in += task.size
                result.bytes_out += written or 0
            else:
                self._errors.append(FileError(task.source, _describe(error), Phase.CONVERTING))
            self._tracker.advance(files=1, nbytes=task.size)

    def _convert_one(self, task: PhotoTask) -> int:
        self._tracker.set_current(task.source)
        return convert_photo(task.source, task.target, self.options)

    def _parallel(self, work: Callable[[PhotoTask], T],
                  tasks: Sequence[PhotoTask]) -> Iterator[tuple[PhotoTask, T | None, OSError | None]]:
        """Run ``work`` for every task on the thread pool and yield ``(task, result, error)`` as each finishes.

        Only a few tasks per worker are queued at a time, so Stop takes effect quickly.
        """
        pending_limit = self.workers * 2
        remaining = iter(tasks)
        with ThreadPoolExecutor(max_workers=self.workers, thread_name_prefix="chameleon") as pool:
            pending: dict[Future[T], PhotoTask] = {}

            def refill() -> None:
                while len(pending) < pending_limit and not self._cancel.is_set():
                    next_task = next(remaining, None)
                    if next_task is None:
                        return
                    pending[pool.submit(work, next_task)] = next_task

            refill()
            while pending:
                done, _ = wait(pending, return_when=FIRST_COMPLETED)
                for future in done:
                    task = pending.pop(future)
                    error = future.exception()
                    if error is None:
                        yield task, future.result(), None
                    elif isinstance(error, OSError):
                        yield task, None, error
                    else:  # a bug, not a bad photo: stop the other workers and fail the job
                        self._cancel.set()
                        raise error
                refill()
        self._check_cancel()

    def _scan_error(self, path: str, error: OSError) -> None:
        self._errors.append(FileError(path, _describe(error), Phase.SCANNING))

    def _check_cancel(self) -> None:
        if self._cancel.is_set():
            raise OperationCancelled


def plan_tasks(found: Sequence[FoundPhoto], options: ConvertOptions,
               exists: Callable[[str], bool] = os.path.lexists) -> tuple[list[PhotoTask], int]:
    """Decide where each photo goes. Returns the tasks and how many photos were skipped.

    Photos of the same job never share a name (the later ones are numbered), whatever
    ``options.existing`` says; that setting only decides about files already on disk.
    """
    tasks: list[PhotoTask] = []
    taken: set[str] = set()
    skipped = 0
    extension = options.output_format.extension
    for photo in found:
        if options.destination is not None:
            target = os.path.join(os.path.abspath(options.destination), os.path.splitext(photo.relative)[0])
        else:
            target = os.path.splitext(photo.source)[0]
        target += extension

        on_disk = exists(target)
        if on_disk and options.existing is ExistingFiles.SKIP and path_key(target) not in taken:
            skipped += 1
            continue
        if path_key(target) in taken or (on_disk and options.existing is ExistingFiles.KEEP_BOTH):
            target = _free_name(target, taken, exists)
        taken.add(path_key(target))
        tasks.append(PhotoTask(len(tasks), photo.source, target, photo.size))
    return tasks, skipped


def _free_name(target: str, taken: set[str], exists: Callable[[str], bool]) -> str:
    """``IMG_0001.jpg`` → ``IMG_0001 (2).jpg``, or the first number that is free."""
    stem, extension = os.path.splitext(target)
    counter = 2
    while True:
        candidate = f"{stem} ({counter}){extension}"
        if path_key(candidate) not in taken and not exists(candidate):
            return candidate
        counter += 1


def _folders_in_order(targets: Iterable[str]) -> list[str]:
    folders: list[str] = []
    seen: set[str] = set()
    for target in targets:
        folder = os.path.dirname(target)
        if path_key(folder) not in seen:
            seen.add(path_key(folder))
            folders.append(folder)
    return folders


def _describe(error: OSError) -> str:
    return error.strerror or str(error) or error.__class__.__name__
