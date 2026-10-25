# Contributing

Thanks for helping improve Chameleon!

## Setting up

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
```

Then run the app with `chameleon` (or `python -m chameleon`), the command line
with `chameleon-cli`, and the tests with `pytest`.

## Guidelines

- **Keep the core free of GUI code.** Anything under `chameleon/core/` must work
  without Tkinter, so it can be tested and used from `chameleon-cli` and scripts.
- **Only the GUI thread touches Tk.** Background code reports through
  `ProgressTracker` and `JobResult`; the window polls them.
- **Never risk the user's photos.** Originals are read-only; output goes through
  `convert_photo` (temporary file plus atomic rename), and `plan_tasks` decides
  every name before anything is written.
- **Keep what the photo carries.** Metadata and the colour profile are copied unless
  the user asks otherwise; add a converter test for anything that touches them.
- **Command-line output stays ASCII.** Legacy Windows consoles can't print arrows,
  ellipses and the like; `test_cli_output_is_plain_ascii` checks it.
- Add or update tests in `tests/` for behaviour changes, and run `pytest` before
  sending a change. Tests make their own HEIC photos; don't commit sample photos.
- Follow the style of the surrounding code: type hints, short docstrings,
  4-space indentation, lines up to about 120 characters.
- Note user-visible changes in `CHANGELOG.md` under an "Unreleased" heading.
- The icon is drawn in code by `scripts/generate_icon.py`. Change the design there
  and run it to regenerate `chameleon/assets/` (the `.ico`, and the 256, 64 and
  48 px PNGs); don't edit the image files by hand.

## Updating dependencies

`requirements.txt` pins the versions the release was tested with;
`pyproject.toml` gives the compatible ranges. After upgrading pillow-heif, run
`pytest`, convert a real iPhone photo, and build the executable once: the hook in
`packaging/hooks/` depends on where pillow-heif installs libheif.

## Releasing

1. Bump `__version__` in `chameleon/__init__.py` and move the changelog entries
   under the new version.
2. Build the executable with `pyinstaller packaging/chameleon.spec` and try it.
3. Tag the release, e.g. `git tag -a v2.1.0`.
