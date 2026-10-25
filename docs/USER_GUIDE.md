# Chameleon user guide

Chameleon makes JPEG (or PNG) copies of HEIC photos, the format iPhones and
iPads use by default and that many programs can't open. Your original photos are
only ever **read**; Chameleon writes new files next to them or in a folder you
choose.

## The window

![The Chameleon window](images/screenshot.png)

The header shows the version you are running (top right), which is useful when
reporting a problem.

### Photos to convert

What to convert: photos, folders, or a mix of both.

- **Add photos…** picks one or more photos (Ctrl- or Shift-click several).
- **Add folders…** picks one or more folders. Select several at once with
  **Ctrl-click** (one by one) or **Shift-click** (a range), then confirm.
  - On Windows this is the normal Windows folder dialog.
  - On macOS and Linux it is Chameleon's own dialog: double-click a folder to open
    it, **Up** goes to the parent folder, and you can type a path in the box at the
    top. **Add selected** with nothing selected adds the folder you are in.
- Folders end with `\` (or `/`) in the list, so you can tell them from photos.
  Anything already in the list is ignored if you add it again.
- **Remove selected** (or the **Delete** key) removes the highlighted entries.
  **Ctrl+A** in the list selects them all. **Clear** empties the list.
- **Include photos in subfolders**: also convert the photos in every folder inside
  the chosen folders. Shortcuts to other folders (symbolic links, junctions) are not
  followed, so nothing is converted twice.

Chameleon converts files ending in `.heic`, `.heif` or `.hif` (in any upper or
lower case) and ignores everything else, so it's fine to add a folder that also
holds videos or JPEGs.

### Save the converted photos

- **Next to the originals**: `D:\Phone\IMG_0001.HEIC` becomes `D:\Phone\IMG_0001.jpg`.
- **In this folder**: everything goes into the folder you choose, which is created
  if it doesn't exist. Subfolders of the folders you added are recreated inside it:

```text
Added:  D:\Phone backup\              Saved in: E:\Converted\
        ├── IMG_0001.HEIC             ├── IMG_0001.jpg
        └── 2024\IMG_0102.HEIC        └── 2024\IMG_0102.jpg
```

Photos added one by one go straight into the chosen folder.

### Options

**Format**

- **JPEG** opens everywhere and keeps files small. **JPEG quality** goes from 50 to
  100: 90 (the default) looks the same as the original for photos; 75–85 makes
  noticeably smaller files that still look good on screen; above 95 the files grow
  a lot for little visible difference.
- **PNG** is lossless, so nothing at all is lost, but files are several times larger
  than the HEIC. Useful when the photo will be edited further.

**Keep the date taken, camera details and colour profile** (on by default)

Copies the photo's EXIF information (date and time taken, camera and lens,
exposure settings, location) and its colour profile to the converted photo. With
it, photo apps sort the copies by when they were taken, and the colours match
what you saw on the phone: iPhones photograph in a wide colour space (Display P3),
and a JPEG without that profile looks dull.

Turn it off to produce photos with no metadata at all. Chameleon then converts the
colours to standard sRGB first, so they still look right.

**Remove the location (GPS) where the photo was taken**

Keeps the date and camera details but removes the GPS position, for photos you
are going to share. (When the details aren't kept at all, there is no location to
remove, so this option is greyed out.)

**If the name is taken**

What to do when the converted photo's name already exists, for example because
you converted the same folder before:

| Choice | What happens |
|--------|--------------|
| Skip the photo | The existing file stays and that photo isn't converted. Running Chameleon again on the same folder only converts new photos. |
| Replace the file | The existing file is overwritten with the new conversion. |
| Keep both | The new photo is saved as `IMG_0001 (2).jpg`. |

Two photos of the same conversion never overwrite each other, whatever you
choose: if `IMG_0001.HEIC` exists in two of the folders you added and both go to
the same destination, the second becomes `IMG_0001 (2).jpg`.

**Worker threads**

How many photos are converted at the same time. Converting is mostly processor
work, so the default, one per processor core (up to 8), is usually the fastest.
Use fewer to keep the computer responsive for other work while converting.

### Progress

While Chameleon runs, the progress box shows:

- **Step 1 of 2: Looking for photos**, with how many have been found so far.
- **Step 2 of 2: Converting photos**, the photo being converted, and a bar with
  photos done, the percentage and the speed in photos per second.
- **Elapsed** time and the estimated time **Remaining**, based on the speed over
  the last few seconds.

**Stop** finishes the photos being converted at that moment and starts no more.
Photos already converted are kept. Because every photo is written under a
temporary name and renamed only when complete, there is never a half-written
photo. To finish later, run it again with **Skip the photo** selected.

When the conversion ends, a summary shows how many photos were found and
converted, how many were skipped, and the sizes before and after. You can then
open the folder with the converted photos.

Your choices (format, quality, options, destination, threads) are remembered for
the next time you open Chameleon.

## The command line

`chameleon-cli` does the same without a window. With no arguments it converts the
HEIC photos in the current folder to JPEG next to the originals:

```bash
chameleon-cli
```

| Option | Meaning |
|--------|---------|
| `PATH …` | Photos or folders to convert (default: the current folder) |
| `-r`, `--recursive` | Also convert photos in subfolders |
| `-o FOLDER`, `--output FOLDER` | Save into this folder, keeping the subfolder structure |
| `--png` | Save PNG instead of JPEG |
| `-q N`, `--quality N` | JPEG quality, 1–100 (default 90) |
| `--no-metadata` | Don't keep the date, camera details and colour profile |
| `--remove-location` | Remove GPS coordinates |
| `--existing skip\|replace\|keep-both` | What to do when the name is taken (default `skip`) |
| `-j N`, `--workers N` | Photos converted at the same time |

It exits with code 0 when everything was converted, 1 when some photos failed (they
are listed), 2 for invalid arguments and 130 when stopped with Ctrl+C.

## Problems with individual photos

A photo that can't be read (damaged, not really a HEIC file, an unsupported
variant) or a folder that can't be opened doesn't stop the conversion. It is
skipped and listed when the job ends; answer **Yes** to see the list, which can be
copied to the clipboard.

## Troubleshooting

**"No HEIC photos found"**
: The files and folders in the list contain no `.heic`, `.heif` or `.hif` files.
  If the photos are in subfolders, tick **Include photos in subfolders**. Photos
  imported from an iPhone with "Automatic" transfer settings may already be JPEGs.

**"No module named tkinter" or "No module named _tkinter"** (Linux)
: Install Tkinter for your Python, e.g. `sudo apt install python3-tk`.

**The colours of the converted photo look different**
: Make sure **Keep the date taken, camera details and colour profile** is on, and
  view the photo in a program that supports colour profiles (Windows Photos, macOS
  Preview and current browsers all do).

**The converted photos have today's date in the file list**
: Chameleon gives each converted photo the original's modification time. Programs
  that sort by "date created" show the day of the conversion; sort by "date taken"
  or "date modified" instead.

**Running it again converted nothing**
: The converted photos already exist and **If the name is taken** is set to **Skip
  the photo**. Choose **Replace the file** to convert them again.

**I see `.….chameleon-partial` files**
: They are left only if Chameleon itself was killed while writing a photo (for
  example from Task Manager or a power cut). They are safe to delete.
