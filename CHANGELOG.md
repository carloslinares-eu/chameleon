# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [2.0.0] - 2026-10-25

Chameleon becomes an app. The single `chameleon.py` script, which converted the
HEIC photos in the current folder, is now the `chameleon` package with a window,
and the script's behaviour lives on as the `chameleon-cli` command.

### Added

- A window in the style of Bloodhound: a list of photos and folders, the choice of
  saving next to the originals or in another folder, options, live progress with
  time remaining, **Stop**, and a list of problems at the end.
- Folders, including their subfolders, with the same structure recreated in a
  destination folder. Several folders can be chosen at once (native multi-select
  dialog on Windows, a built-in dialog elsewhere).
- PNG output, and adjustable JPEG quality (default 90).
- An option to remove the location (GPS) from the photos.
- A choice for names that are already taken: skip, replace or keep both.
- Photos are converted in parallel on a configurable number of worker threads.
- The window remembers your choices.
- `chameleon-cli` with options for everything the window does.
- Application icon (window, taskbar and executable) and a header with the version.
- Installable package (`pip install .`), `python -m chameleon`, and a PyInstaller
  recipe for a single windowed executable.
- Documentation (README, user guide, architecture notes), MIT license and a test suite.

### Changed

- Converted photos keep their EXIF data (date taken, camera details, location), their
  colour profile and their modification time. The script dropped all of them, so
  copies lost their date and iPhone photos (Display P3) looked dull.
- The default JPEG quality is 90 instead of Pillow's 75.
- Existing JPEGs are no longer overwritten silently; by default those photos are skipped.
- Each photo is written under a temporary name and renamed when complete.
- `.heif` and `.hif` files are converted as well as `.heic`, in any letter case.
- Dependencies updated: Pillow 12.0.0 → 13.0.0, pillow-heif 1.1.1 → 1.8.1. Python 3.10+.
- `pyproject.toml` replaces `setup.py`. The old `pyproject.toml` pointed at a
  `heic_to_jpg` module that didn't exist, so the installed command didn't work.

### Fixed

- On Windows every photo was converted twice: the script searched for `*.heic` and
  then `*.HEIC`, and Windows file names ignore case, so both searches found every photo.
- A photo that failed to convert could leave a broken, half-written JPEG behind.
- `requirements.txt` was saved as UTF-16, which GitHub and most tools other than pip
  show as garbage; it is plain UTF-8 again.

### Removed

- PyInstaller's `build/` and `dist/` output (about 45 MB, including a copy of the
  executable) is no longer in the repository; build it with `packaging/chameleon.spec`.
- The PyCharm `.idea/` folder is no longer tracked.
