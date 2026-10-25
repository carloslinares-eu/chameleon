"""Smoke tests for the window. Skipped where no display is available."""

from __future__ import annotations

import os
import tkinter as tk

import pytest

from chameleon import __version__
from chameleon.core import ExistingFiles, JobResult, OutputFormat, Phase, ProgressSnapshot
from chameleon.core.settings import Settings


@pytest.fixture(scope="module")
def tk_root():
    # One Tk interpreter per process: creating a second one can fail to find tk.tcl in some virtualenvs.
    try:
        interpreter = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"no display: {exc}")
    interpreter.withdraw()
    yield interpreter
    interpreter.destroy()


@pytest.fixture
def window(tk_root, tmp_path, monkeypatch):
    from chameleon.gui.main_window import MainWindow

    monkeypatch.setattr("chameleon.core.settings.settings_path", lambda: tmp_path / "settings.json")
    top = tk.Toplevel(tk_root)
    yield MainWindow(top, settings=Settings())
    top.destroy()


def test_header_list_and_counts(window, tmp_path):
    assert window.version_label.cget("text") == f"v{__version__}"
    assert window._logo is not None and window._logo.width() in (48, 64)
    photo = tmp_path / "a.heic"
    photo.write_bytes(b"")
    assert window.source_list.add([str(tmp_path), str(photo), str(tmp_path)]) == 2
    assert window.source_list.listbox.get(0).endswith(os.sep)  # folders are marked with a separator
    assert window.source_count.cget("text") == "1 folder, 1 photo"


def test_options_follow_the_controls(window):
    window.output_format.set("png")
    window.keep_metadata.set(False)
    window.remove_location.set(True)
    window.next_to_originals.set(False)
    window.destination.set("D:/JPG")
    window.existing.set("Keep both (number the new one)")
    options = window.options()
    assert options.output_format is OutputFormat.PNG and options.destination == "D:/JPG"
    assert options.existing is ExistingFiles.KEEP_BOTH
    assert not options.remove_location  # nothing to remove when no metadata is kept


def test_controls_enable_and_disable(window):
    window.output_format.set("png")
    window._update_quality()
    assert window.quality_scale.instate(["disabled"])
    window.keep_metadata.set(False)
    window._update_location()
    assert str(window.location_check.cget("state")) == "disabled"
    window.next_to_originals.set(True)
    window._update_destination()
    assert str(window.destination_entry.cget("state")) == "disabled"


def test_progress_rendering_and_summary(window):
    from chameleon.gui.main_window import describe_result

    window._render(ProgressSnapshot(
        phase=Phase.CONVERTING, files_done=10, files_total=40, bytes_done=25, bytes_total=100,
        elapsed=75, rate=2.5, eta=30, current_file="C:/photos/IMG_0001.heic",
    ))
    assert window.status_text.get() == "Step 2 of 2: Converting photos"
    assert "10 of 40 photos" in window.detail_text.get()
    assert window.remaining_text.get() == "Remaining: ~00:00:30"
    summary = describe_result(JobResult(photos_found=40, converted=38, skipped_existing=2, elapsed=80))
    assert "Converted: 38" in summary and "already there: 2" in summary


def test_a_run_saves_settings_and_reports(window, tmp_path, monkeypatch):
    shown = []
    for name in ("showinfo", "showwarning", "showerror", "askyesno"):
        monkeypatch.setattr(f"chameleon.gui.main_window.messagebox.{name}",
                            lambda title, message, **_options: shown.append(title))
    window.output_format.set("png")
    window.source_list.add([str(tmp_path)])
    window._start()
    window._thread.join(10)
    window._poll()  # what the window's timer does
    assert Settings.load(tmp_path / "settings.json").output_format == "png"
    assert shown == ["Nothing to convert"] and window.status_text.get() == "No HEIC photos found."
