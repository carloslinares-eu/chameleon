# Architecture

Chameleon is split into a GUI-free **core** that does the work, a Tkinter **gui**
that drives it, and a small **cli** that drives it from a terminal. The core can
be used from scripts or tests without a display.

```text
chameleon/
├── app.py            main(): Windows DPI/taskbar setup, Tk root, icon, MainWindow
├── cli.py            main() for chameleon-cli: argparse, runs a job, prints progress
├── core/
│   ├── engine.py     ConversionJob: the 2 phases and the thread pool; plan_tasks()
│   ├── converter.py  convert_photo(): decode, keep or strip metadata, save atomically
│   ├── scanner.py    find_photos(): HEIC files in the chosen files and folders
│   ├── progress.py   ProgressTracker: thread-safe counters, photos/s, ETA
│   ├── settings.py   Settings: remembered choices (JSON in the user's settings folder)
│   ├── models.py     Phase, ConvertOptions, OutputFormat, ExistingFiles, FoundPhoto,
│   │                 PhotoTask, ProgressSnapshot, JobResult, FileError
│   └── errors.py     OperationCancelled
├── gui/
│   ├── main_window.py    layout, options, starting/stopping jobs, rendering progress
│   ├── widgets.py        SourceList, TextProgressBar, ErrorListDialog
│   ├── folder_picker.py  ask_directories(): native on Windows, Tk dialog elsewhere
│   ├── _win_folder_dialog.py  IFileOpenDialog via ctypes (multi-select folders)
│   └── icon.py           window icon and the header logo
└── utils/
    ├── formatting.py  sizes, durations, path shortening
    └── paths.py       case-aware path comparison
```

The widgets, folder picker, progress model and formatting helpers come from
[Bloodhound](https://github.com/carloslinares-eu/bloodhound-dedupe), which uses
the same structure.

## Threads

```text
 GUI thread (Tk mainloop)          job thread                    worker pool (N threads)
 ───────────────────────          ──────────                     ───────────────────────
 Convert ─► ConversionJob(...)
            Thread(job.run) ─────► scan, plan_tasks()
                                   convert phase ── submit ────► convert_photo()
 every 150 ms:                     ◄──── (task, size, error) ────┘
   job.snapshot() ◄── lock ──────── tracker.advance()
   render labels/bar
 Stop ─► job.cancel() ── Event ──► no new photos are submitted
 thread finished? ─► job.result ─► summary dialog
```

- **The GUI thread** never touches files. It starts a `ConversionJob` on a
  background thread and polls `job.snapshot()` every 150 ms with `after()`.
  Tkinter isn't thread-safe, so nothing else calls into Tk.
- **The job thread** runs the phases and owns the bookkeeping (`JobResult`, the
  list of problems). Workers only return the size written or raise, so the only
  shared state is the progress tracker, behind its lock.
- **The worker pool** (`ThreadPoolExecutor`) decodes and encodes. libheif and
  Pillow's encoders release the GIL while they work, so threads use every core.
  Only `workers × 2` photos are queued at a time (`ConversionJob._parallel`), which
  lets Stop take effect after the photos in progress.

`chameleon-cli` uses the same job: it runs `job.run()` on a thread, prints a
progress line from `snapshot()` twice a second when the output is a terminal, and
turns Ctrl+C into `job.cancel()`. Its messages stay ASCII because legacy Windows
consoles and redirected output can't encode arrows or ellipses.

## Output names

`plan_tasks()` decides every output path before anything is converted:

1. The name is the photo's name with `.jpg` or `.png`. With a destination folder,
   the photo's path relative to the folder it was found in is kept below it.
2. A path is *taken* if another photo of this job already got it, or a file exists
   there. Paths taken within the job are always numbered (`IMG_0001 (2).jpg`), so a
   job never overwrites its own output.
3. For files already on disk, `ExistingFiles` decides: skip the photo (counted in
   `JobResult.skipped_existing`), replace the file, or number the new one.

Planning first means the progress bar knows the total from the start, and the
summary can say how many photos were skipped without trying to convert them.

## Converting a photo

`convert_photo()` opens the photo with Pillow, through the HEIF plugin that
pillow-heif registers:

- **Orientation**: pillow-heif applies the photo's rotation while decoding and
  resets the EXIF orientation to 1, so copying the EXIF can't rotate the photo a
  second time.
- **Metadata kept**: the EXIF block (minus the GPS block `0x8825` when the location
  is removed), the ICC colour profile and, for JPEG, the XMP packet. XMP can repeat
  the GPS position, so it is dropped when the location is removed.
- **Metadata not kept**: the pixels are converted from the photo's profile to sRGB
  with `ImageCms`, and nothing else is written, so colours stay right without a profile.
- **Pixels**: JPEG has no transparency, so images with an alpha channel are put on
  white; PNG keeps it.
- **Writing**: the result goes to `.<name>.chameleon-partial` in the target folder
  and is moved into place with `os.replace`, then gets the original's access and
  modification times (`os.utime`). The partial file is removed on any error.

Decoders report broken files with `ValueError`, `RuntimeError`, `SyntaxError` or
Pillow's `UnidentifiedImageError`; `convert_photo` turns all of them into `OSError`,
which the engine records as a problem with that photo. Any other exception is a bug:
it stops the job and is shown as an unexpected error.

## Progress, speed and time remaining

`ProgressTracker` keeps per-phase counters (`files_done/total`, `bytes_done/total`)
under one lock. Workers report each finished photo with its input size. Every 0.25 s
a sample `(time, bytes, files)` is recorded and samples older than 8 s are dropped.
The speed shown is photos per second over that window; the time remaining is the
bytes still to read divided by the byte rate, because a 4 MB photo takes about twice
as long as a 2 MB one.

## Packaging

`packaging/chameleon.spec` builds a single windowed executable from
`chameleon/__main__.py`, with the assets and icon. pillow-heif's native library is
installed next to the package (`site-packages/libheif-*.dll` on Windows,
`pillow_heif.libs/` on Linux), where PyInstaller doesn't look, so
`packaging/hooks/hook-pillow_heif.py` collects it.

## Tests

`tests/` uses pytest. `conftest.py` writes real HEIC photos with pillow-heif (with a
date, GPS position, orientation and sRGB profile), so no sample files are needed.
The converter tests check metadata, rotation, formats, timestamps and broken files;
the engine tests run complete jobs (destinations, name clashes, stopping, problems);
the CLI is run in-process; the GUI smoke tests are skipped when no display is available.
