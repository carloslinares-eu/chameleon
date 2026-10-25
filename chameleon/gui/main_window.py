"""The Chameleon main window."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk

from chameleon import __app_name__, __version__
from chameleon.core import (
    MAX_WORKERS,
    ConversionJob,
    ConvertOptions,
    ExistingFiles,
    JobResult,
    OutputFormat,
    Phase,
    ProgressSnapshot,
    default_workers,
)
from chameleon.core.scanner import HEIF_EXTENSIONS
from chameleon.core.settings import Settings
from chameleon.gui.folder_picker import ask_directories
from chameleon.gui.icon import load_image
from chameleon.gui.widgets import ErrorListDialog, SourceList, TextProgressBar
from chameleon.utils.formatting import format_bytes, format_duration, shorten_path

log = logging.getLogger(__name__)

POLL_INTERVAL_MS = 150

PHASE_TITLES = {
    Phase.SCANNING: "Looking for photos",
    Phase.CONVERTING: "Converting photos",
}
PHASE_ORDER = tuple(PHASE_TITLES)

EXISTING_LABELS = {
    ExistingFiles.SKIP: "Skip the photo",
    ExistingFiles.REPLACE: "Replace the file",
    ExistingFiles.KEEP_BOTH: "Keep both (number the new one)",
}
PHOTO_TYPES = [("HEIC photos", " ".join(f"*{ext}" for ext in sorted(HEIF_EXTENSIONS))), ("All files", "*.*")]

START_COLORS = {"background": "#4CAF50", "activebackground": "#43A047"}
STOP_COLORS = {"background": "#E53935", "activebackground": "#C62828"}
DISABLED_BACKGROUND = "#BDBDBD"
MUTED = "#5F5F5F"


class MainWindow(ttk.Frame):
    """Photo list, destination, options, progress readout and Convert/Stop buttons."""

    def __init__(self, root: tk.Tk | tk.Toplevel, settings: Settings | None = None):
        super().__init__(root, padding=(16, 12, 16, 16))
        self.root = root
        self.settings = settings or Settings.load()
        self.grid(row=0, column=0, sticky="nsew")
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        s = self.settings
        self.include_subfolders = tk.BooleanVar(value=s.include_subfolders)
        self.next_to_originals = tk.BooleanVar(value=s.save_next_to_originals)
        self.destination = tk.StringVar(value=s.destination)
        self.output_format = tk.StringVar(value=s.output_format if s.output_format in ("jpeg", "png") else "jpeg")
        self.quality = tk.IntVar(value=max(1, min(100, s.quality)))
        self.keep_metadata = tk.BooleanVar(value=s.keep_metadata)
        self.remove_location = tk.BooleanVar(value=s.remove_location)
        existing = next((choice for choice in ExistingFiles if choice.value == s.existing), ExistingFiles.SKIP)
        self.existing = tk.StringVar(value=EXISTING_LABELS[existing])
        self.workers = tk.IntVar(value=s.workers if 1 <= s.workers <= MAX_WORKERS else default_workers())
        self.last_browsed_dir = s.last_folder if os.path.isdir(s.last_folder) else os.path.expanduser("~")

        self._job: ConversionJob | None = None
        self._thread: threading.Thread | None = None
        self._job_error: BaseException | None = None
        self._quit_when_stopped = False

        base_font = tkfont.nametofont("TkDefaultFont")
        self._title_font = base_font.copy()
        self._title_font.configure(size=base_font.cget("size") + 6, weight="bold")
        self._bold_font = base_font.copy()
        self._bold_font.configure(weight="bold")

        self._build_header(row=0)
        self._build_sources(row=1)
        self._build_destination(row=2)
        self._build_options(row=3)
        self._build_progress(row=4)
        self._build_actions(row=5)

        self._set_running(False)
        self._show_ready()
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        root.update_idletasks()
        root.minsize(root.winfo_reqwidth(), root.winfo_reqheight())

    # -- layout ------------------------------------------------------------------

    def _build_header(self, row: int) -> None:
        header = ttk.Frame(self)
        header.grid(row=row, column=0, sticky="ew", pady=(0, 12))
        header.columnconfigure(1, weight=1)

        large = self.root.winfo_fpixels("1i") >= 120  # pick the sharper logo on high-DPI screens
        self._logo = load_image("chameleon-64.png" if large else "chameleon-48.png", master=self.root)
        if self._logo is not None:
            ttk.Label(header, image=self._logo).grid(row=0, column=0, rowspan=2, padx=(0, 12))
        ttk.Label(header, text=__app_name__, font=self._title_font).grid(row=0, column=1, sticky="sw")
        self.version_label = ttk.Label(header, text=f"v{__version__}", foreground=MUTED)
        self.version_label.grid(row=0, column=2, sticky="ne")
        ttk.Label(
            header,
            text="Converts iPhone HEIC photos to JPEG or PNG, keeping their date, colours and details.",
            foreground=MUTED,
        ).grid(row=1, column=1, columnspan=2, sticky="nw")

    def _build_sources(self, row: int) -> None:
        box = ttk.LabelFrame(self, text="Photos to convert", padding=10)
        box.grid(row=row, column=0, sticky="nsew")
        box.columnconfigure(0, weight=1)
        box.rowconfigure(0, weight=1)

        self.source_list = SourceList(box, height=7, on_change=self._update_source_count)
        self.source_list.grid(row=0, column=0, sticky="nsew")

        buttons = ttk.Frame(box)
        buttons.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.add_photos_button = ttk.Button(buttons, text="Add photos…", command=self._add_photos)
        self.add_photos_button.pack(side="left")
        self.add_folders_button = ttk.Button(buttons, text="Add folders…", command=self._add_folders)
        self.add_folders_button.pack(side="left", padx=(6, 0))
        self.remove_button = ttk.Button(buttons, text="Remove selected", command=self.source_list.remove_selected)
        self.remove_button.pack(side="left", padx=(6, 0))
        self.clear_button = ttk.Button(buttons, text="Clear", command=self.source_list.clear)
        self.clear_button.pack(side="left", padx=(6, 0))
        self.source_count = ttk.Label(buttons, foreground=MUTED)
        self.source_count.pack(side="right")

        self.subfolders_check = ttk.Checkbutton(box, text="Include photos in subfolders",
                                                variable=self.include_subfolders)
        self.subfolders_check.grid(row=2, column=0, sticky="w", pady=(8, 0))
        self._update_source_count()

    def _build_destination(self, row: int) -> None:
        box = ttk.LabelFrame(self, text="Save the converted photos", padding=10)
        box.grid(row=row, column=0, sticky="ew", pady=(10, 0))
        box.columnconfigure(1, weight=1)
        self.next_to_radio = ttk.Radiobutton(box, text="Next to the originals", value=True,
                                             variable=self.next_to_originals, command=self._update_destination)
        self.next_to_radio.grid(row=0, column=0, columnspan=3, sticky="w")
        self.folder_radio = ttk.Radiobutton(box, text="In this folder:", value=False,
                                            variable=self.next_to_originals, command=self._update_destination)
        self.folder_radio.grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.destination_entry = ttk.Entry(box, textvariable=self.destination)
        self.destination_entry.grid(row=1, column=1, sticky="ew", padx=(6, 0), pady=(4, 0))
        self.browse_button = ttk.Button(box, text="Browse…", command=self._choose_destination)
        self.browse_button.grid(row=1, column=2, padx=(6, 0), pady=(4, 0))
        ttk.Label(box, text="Subfolders are recreated inside it.", foreground=MUTED).grid(
            row=2, column=1, columnspan=2, sticky="w", padx=(6, 0))

    def _build_options(self, row: int) -> None:
        box = ttk.LabelFrame(self, text="Options", padding=10)
        box.grid(row=row, column=0, sticky="ew", pady=(10, 0))
        box.columnconfigure(3, weight=1)

        ttk.Label(box, text="Format:").grid(row=0, column=0, sticky="w")
        self.jpeg_radio = ttk.Radiobutton(box, text="JPEG", value="jpeg", variable=self.output_format,
                                          command=self._update_quality)
        self.jpeg_radio.grid(row=0, column=1, sticky="w", padx=(6, 0))
        self.png_radio = ttk.Radiobutton(box, text="PNG (lossless, larger files)", value="png",
                                         variable=self.output_format, command=self._update_quality)
        self.png_radio.grid(row=0, column=2, columnspan=2, sticky="w", padx=(12, 0))

        ttk.Label(box, text="JPEG quality:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        quality = ttk.Frame(box)
        quality.grid(row=1, column=1, columnspan=3, sticky="ew", padx=(6, 0), pady=(6, 0))
        self.quality_scale = ttk.Scale(quality, from_=50, to=100, orient="horizontal", length=200,
                                       command=lambda value: self.quality.set(round(float(value))))
        self.quality_scale.set(self.quality.get())
        self.quality_scale.pack(side="left")
        self.quality_label = ttk.Label(quality, textvariable=self.quality, width=4)
        self.quality_label.pack(side="left", padx=(6, 0))
        ttk.Label(quality, text="90 looks the same as the original; lower makes smaller files.",
                  foreground=MUTED).pack(side="left")

        self.metadata_check = ttk.Checkbutton(
            box, text="Keep the date taken, camera details and colour profile",
            variable=self.keep_metadata, command=self._update_location)
        self.metadata_check.grid(row=2, column=0, columnspan=4, sticky="w", pady=(8, 0))
        self.location_check = ttk.Checkbutton(box, text="Remove the location (GPS) where the photo was taken",
                                              variable=self.remove_location)
        self.location_check.grid(row=3, column=0, columnspan=4, sticky="w", padx=(20, 0))

        ttk.Label(box, text="If the name is taken:").grid(row=4, column=0, sticky="w", pady=(8, 0))
        self.existing_box = ttk.Combobox(box, textvariable=self.existing, state="readonly", width=30,
                                         values=list(EXISTING_LABELS.values()))
        self.existing_box.grid(row=4, column=1, columnspan=2, sticky="w", padx=(6, 0), pady=(8, 0))

        ttk.Label(box, text="Worker threads:").grid(row=5, column=0, sticky="w", pady=(6, 0))
        self.workers_spinbox = ttk.Spinbox(box, from_=1, to=MAX_WORKERS, textvariable=self.workers, width=4)
        self.workers_spinbox.grid(row=5, column=1, sticky="w", padx=(6, 0), pady=(6, 0))
        ttk.Label(box, text="Photos converted at the same time; one per processor core is fastest.",
                  foreground=MUTED).grid(row=5, column=2, columnspan=2, sticky="w", padx=(12, 0), pady=(6, 0))

    def _build_progress(self, row: int) -> None:
        box = ttk.LabelFrame(self, text="Progress", padding=10)
        box.grid(row=row, column=0, sticky="ew", pady=(10, 0))
        box.columnconfigure(0, weight=1)

        self.status_text = tk.StringVar()
        self.detail_text = tk.StringVar()
        self.elapsed_text = tk.StringVar()
        self.remaining_text = tk.StringVar()

        # width=1 stops long text from widening the window; the grid stretches the labels instead.
        ttk.Label(box, textvariable=self.status_text, font=self._bold_font, width=1).grid(row=0, column=0, sticky="ew")
        ttk.Label(box, textvariable=self.detail_text, foreground=MUTED, width=1).grid(row=1, column=0, sticky="ew")
        self.progress_bar = TextProgressBar(box)
        self.progress_bar.grid(row=2, column=0, sticky="ew", pady=6)

        times = ttk.Frame(box)
        times.grid(row=3, column=0, sticky="ew")
        ttk.Label(times, textvariable=self.elapsed_text).pack(side="left")
        ttk.Label(times, textvariable=self.remaining_text).pack(side="right")

    def _build_actions(self, row: int) -> None:
        bar = ttk.Frame(self)
        bar.grid(row=row, column=0, sticky="e", pady=(12, 0))
        button_style = {
            "foreground": "white",
            "disabledforeground": "#F5F5F5",
            "activeforeground": "white",
            "font": self._bold_font,
            "relief": "flat",
            "borderwidth": 0,
            "padx": 16,
            "pady": 6,
            "cursor": "hand2",
        }
        self.start_button = tk.Button(bar, text="Convert photos", command=self._start, **button_style)
        self.start_button.pack(side="left")
        self.stop_button = tk.Button(bar, text="Stop", width=8, command=self._stop, **button_style)
        self.stop_button.pack(side="left", padx=(8, 0))

    # -- user actions ------------------------------------------------------------

    def _add_photos(self) -> None:
        paths = filedialog.askopenfilenames(parent=self.root, title="Select HEIC photos to convert",
                                            initialdir=self.last_browsed_dir, filetypes=PHOTO_TYPES)
        if paths:
            self.last_browsed_dir = os.path.dirname(os.path.normpath(paths[0]))
            self.source_list.add(paths)

    def _add_folders(self) -> None:
        paths = ask_directories(self.root, "Select folders with photos to convert", self.last_browsed_dir)
        if paths:
            self.last_browsed_dir = os.path.dirname(os.path.normpath(paths[0])) or paths[0]
            self.source_list.add(paths)

    def _choose_destination(self) -> None:
        folder = filedialog.askdirectory(
            parent=self.root, title="Save the converted photos in", initialdir=self.last_browsed_dir, mustexist=False
        )
        if folder:
            self.destination.set(os.path.normpath(folder))
            self.next_to_originals.set(False)
            self._update_destination()

    def options(self) -> ConvertOptions:
        """The options as currently set in the window."""
        existing = next(choice for choice, label in EXISTING_LABELS.items() if label == self.existing.get())
        return ConvertOptions(
            output_format=OutputFormat(self.output_format.get()),
            quality=self.quality.get(),
            keep_metadata=self.keep_metadata.get(),
            remove_location=self.keep_metadata.get() and self.remove_location.get(),
            destination=None if self.next_to_originals.get() else self.destination.get(),
            include_subfolders=self.include_subfolders.get(),
            existing=existing,
        )

    def _start(self) -> None:
        try:
            workers = int(self.workers.get())
        except (tk.TclError, ValueError):
            workers = default_workers()
        workers = max(1, min(MAX_WORKERS, workers))
        self.workers.set(workers)

        options = self.options()
        try:
            job = ConversionJob(self.source_list.paths, options, workers=workers)
        except ValueError as exc:
            messagebox.showwarning("Can't start yet", str(exc), parent=self.root)
            return
        self._save_settings(options, workers)

        thread = threading.Thread(target=self._run_job, args=(job,), name="chameleon-job", daemon=True)
        self._job, self._job_error, self._thread = job, None, thread
        self._set_running(True)
        thread.start()
        self.after(POLL_INTERVAL_MS, self._poll)

    def _stop(self) -> None:
        if self._job is not None and not self._job.cancel_requested:
            self._job.cancel()
            self.stop_button.configure(state="disabled", text="Stopping…", background=DISABLED_BACKGROUND)

    def _on_close(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            if not messagebox.askyesno(
                "Quit Chameleon?",
                "Photos are still being converted. Stop and quit?\n\nPhotos already converted are kept.",
                parent=self.root,
            ):
                return
            self._quit_when_stopped = True
            self._stop()
            return
        self.root.destroy()

    # -- running a job -----------------------------------------------------------

    def _run_job(self, job: ConversionJob) -> None:
        """Body of the background thread. The GUI only ever touches the job through snapshot()/cancel()."""
        try:
            job.run()
        except BaseException as exc:  # reported on the GUI thread by _finish
            log.exception("The job failed")
            self._job_error = exc

    def _poll(self) -> None:
        if self._job is None or self._thread is None:
            return
        self._render(self._job.snapshot())
        if self._thread.is_alive():
            self.after(POLL_INTERVAL_MS, self._poll)
        else:
            self._finish()

    def _render(self, snap: ProgressSnapshot) -> None:
        if snap.phase in PHASE_TITLES:
            step = PHASE_ORDER.index(snap.phase) + 1
            status = f"Step {step} of {len(PHASE_ORDER)}: {PHASE_TITLES[snap.phase]}"
            if self._job is not None and self._job.cancel_requested:
                status = "Stopping… finishing the photos already started"
            self.status_text.set(status)

        current = f"  ·  {shorten_path(snap.current_file, 90)}" if snap.current_file else ""
        if snap.phase is Phase.SCANNING:
            self.detail_text.set(f"{snap.files_done:,} photos found{current}")
            self.progress_bar.start_pulse()
            self.progress_bar.set_text(f"{snap.files_done:,} photos ({format_bytes(snap.bytes_done)}) found so far")
            self.remaining_text.set("Remaining: estimating…")
        elif snap.phase is Phase.CONVERTING:
            self.detail_text.set(f"{snap.files_done:,} of {snap.files_total:,} photos{current}")
            text = f"{snap.files_done:,} of {snap.files_total:,} photos  ({snap.fraction:.1%})"
            if snap.rate:
                text += f"  ·  {snap.rate:.1f} photos/s"
            self.progress_bar.set(snap.fraction, text)
            eta = "estimating…" if snap.eta is None else f"~{format_duration(snap.eta)}"
            self.remaining_text.set(f"Remaining: {eta}")
        self.elapsed_text.set(f"Elapsed: {format_duration(snap.elapsed)}")

    def _finish(self) -> None:
        job, error = self._job, self._job_error
        self._job = self._thread = None
        if job is None:
            return
        self._set_running(False)
        if self._quit_when_stopped:
            self.root.destroy()
            return

        result = job.result
        if error is not None or result is None:
            reason = error if error is not None else "the job ended without a result"
            self.status_text.set("Something went wrong.")
            self.detail_text.set(f"{reason}")
            self.progress_bar.set(0.0, "")
            self.remaining_text.set("")
            messagebox.showerror("Chameleon", f"The conversion stopped because of an unexpected error:\n\n{reason}",
                                 parent=self.root)
            return

        self.elapsed_text.set(f"Elapsed: {format_duration(result.elapsed)}")
        self.remaining_text.set("")
        if result.cancelled:
            self.status_text.set("Stopped.")
            self.detail_text.set(f"{result.converted:,} photos converted before stopping.")
            self.progress_bar.set(job.snapshot().fraction, "Stopped")
            title = "Stopped"
        elif result.photos_found == 0:
            self.status_text.set("No HEIC photos found.")
            self.detail_text.set("The files and folders in the list contain no .heic, .heif or .hif photos.")
            self.progress_bar.set(0.0, "")
            title = "Nothing to convert"
        else:
            self.status_text.set("Done!")
            self.detail_text.set(f"{result.converted:,} photos converted  ·  "
                                 f"{format_bytes(result.bytes_in)} → {format_bytes(result.bytes_out)}")
            self.progress_bar.set(1.0, f"{result.converted:,} photos converted")
            title = "Finished"

        summary = describe_result(result)
        if result.errors:
            if messagebox.askyesno(title, f"{summary}\n\nShow the list of problems?", icon="warning",
                                   parent=self.root):
                ErrorListDialog(self.root, result.errors)
        elif result.converted and result.output_folders:
            if messagebox.askyesno(title, f"{summary}\n\nOpen the folder with the converted photos?",
                                   parent=self.root):
                open_folder(result.output_folders[0])
        else:
            messagebox.showinfo(title, summary, parent=self.root)

    # -- state -------------------------------------------------------------------

    def _set_running(self, running: bool) -> None:
        idle_state = "disabled" if running else "normal"
        for widget in (self.add_photos_button, self.add_folders_button, self.remove_button, self.clear_button,
                       self.subfolders_check, self.next_to_radio, self.folder_radio, self.jpeg_radio,
                       self.png_radio, self.metadata_check, self.workers_spinbox):
            widget.configure(state=idle_state)
        self.existing_box.configure(state="disabled" if running else "readonly")
        self.source_list.set_enabled(not running)
        self.start_button.configure(
            state=idle_state, background=DISABLED_BACKGROUND if running else START_COLORS["background"],
            activebackground=START_COLORS["activebackground"],
        )
        self.stop_button.configure(
            state="normal" if running else "disabled", text="Stop",
            background=STOP_COLORS["background"] if running else DISABLED_BACKGROUND,
            activebackground=STOP_COLORS["activebackground"],
        )
        self._update_destination(running)
        self._update_quality(running)
        self._update_location(running)

    def _update_destination(self, running: bool = False) -> None:
        state = "disabled" if running or self.next_to_originals.get() else "normal"
        self.destination_entry.configure(state=state)
        self.browse_button.configure(state="disabled" if running else "normal")

    def _update_quality(self, running: bool = False) -> None:
        jpeg = self.output_format.get() == "jpeg"
        self.quality_scale.state(["!disabled"] if jpeg and not running else ["disabled"])

    def _update_location(self, running: bool = False) -> None:
        enabled = self.keep_metadata.get() and not running  # without metadata there is no location to remove
        self.location_check.configure(state="normal" if enabled else "disabled")

    def _show_ready(self) -> None:
        self.status_text.set("Ready.")
        self.detail_text.set("Add the photos or folders to convert, choose where to save them, then Convert.")
        self.progress_bar.set(0.0, "")
        self.elapsed_text.set(f"Elapsed: {format_duration(0)}")
        self.remaining_text.set("")

    def _update_source_count(self) -> None:
        folders = self.source_list.folder_count
        photos = len(self.source_list.paths) - folders
        parts = []
        if folders:
            parts.append(f"{folders} folder{'s' if folders != 1 else ''}")
        if photos:
            parts.append(f"{photos} photo{'s' if photos != 1 else ''}")
        self.source_count.configure(text=", ".join(parts) or "Nothing added yet")

    def _save_settings(self, options: ConvertOptions, workers: int) -> None:
        s = self.settings
        s.output_format = options.output_format.value
        s.quality = options.quality
        s.keep_metadata = options.keep_metadata
        s.remove_location = self.remove_location.get()
        s.existing = options.existing.value
        s.include_subfolders = options.include_subfolders
        s.save_next_to_originals = self.next_to_originals.get()
        s.destination = self.destination.get()
        s.workers = workers
        s.last_folder = self.last_browsed_dir
        s.save()


def describe_result(result: JobResult) -> str:
    """The summary shown when a job ends."""
    lines = []
    if result.cancelled:
        lines += ["The conversion was stopped before it finished. Photos converted so far are kept.", ""]
    lines += [
        f"Photos found: {result.photos_found:,}",
        f"Converted: {result.converted:,} ({format_bytes(result.bytes_in)} → {format_bytes(result.bytes_out)})",
    ]
    if result.skipped_existing:
        lines.append(f"Skipped, converted file already there: {result.skipped_existing:,}")
    if result.errors:
        lines.append(f"Problems: {len(result.errors):,} photo(s) or folder(s) could not be converted")
    lines.append(f"Time: {format_duration(result.elapsed)}")
    return "\n".join(lines)


def open_folder(path: str) -> None:
    """Show a folder in Explorer, Finder or the desktop's file manager."""
    try:
        if sys.platform == "win32":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except OSError:
        log.warning("Could not open %s", path, exc_info=True)
