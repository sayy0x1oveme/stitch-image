# Manual Screenshot Stitcher

A standalone desktop tool for stitching scrolling chat screenshots with manual
crop boundaries and optional solid-white redactions. No OCR or automatic matching.

## Requirements

- Python **3.10 or newer**.
- Tkinter (included in the standard Windows Python installer).
- Pillow. The release dependency is pinned to the version used for testing.

This folder contains source. A separate **Windows x64 executable ZIP** is available for users who do not want to install Python. Extract that ZIP and double-click ManualScreenshotStitcher.exe. It does not require Codex or
any account, and it performs image processing locally.

## Quick start on Windows

Install Python with Tkinter and the `py` launcher, extract this folder, then open
PowerShell in the extracted folder:

```powershell
py -3 -m pip install -r requirements.txt
py -3 manual_stitch.py
```

After installing the dependency, you can also double-click **run_windows.cmd**.
The launcher checks the Python version and dependencies, and keeps a console open for diagnostics. `run_windows.cmd` is a batch launcher, not an executable binary. If `py` is unavailable, use
`python` in the two commands above.

On macOS/Linux, run `python3 -m pip install -r requirements.txt`, followed by
`python3 manual_stitch.py`. Tkinter may need installation through your system
package manager. Windows is the platform used for GUI verification; other
platforms have not been tested.

## Workflow

1. **Select Screenshots** loads files in filename order.
2. Adjust each image's START and END to keep exactly the desired rows.
3. Use **Preview Seam** to inspect the join between adjacent kept crops.
4. Use Previous/Next or Confirm & Next to navigate; edits stay with each image.
5. **Save Project** saves edits for later. **Open Project** restores them.
6. **Build Final Image** shows a crop summary, then offers **Save PNG**.

Each image owns its interval `[START, END)`. Defaults are 0 and original height.
All output is cropped from original images, never resized GUI previews.

## Controls

| Action | Control |
| --- | --- |
| Set START | Left-click or left-drag |
| Set END | Right-click or right-drag |
| Exact row adjustment | START/END fields and Set buttons |
| Temporary white mask | Shift + left-drag in Auto mode |
| Draw masks without Shift | **MASK Mode**, then left-drag |
| Return to cropping / recover stuck modifier | **CROP Mode** |
| Restore Shift controls | **Use Shift (Auto)** |
| Select existing mask | Click inside it |
| Remove selected mask | Delete / Backspace |
| Undo mask creation/deletion | Ctrl+Z |
| Cancel unfinished mask | Esc |
| Navigate pairs | Left / Right |
| Confirm and advance | Enter |
| Preview seam | P |
| Reset visible crops | R |

CROP and MASK buttons override Shift until Auto is selected. The top mode bar
shows the effective mode and Shift state. Normal left-click inside an existing
mask selects it instead of moving START; numeric fields remain available.

Masks are opaque pure white and have no saved-box outlines. The unfinished
rectangle has a temporary guide. Masks remain attached to their source-image
coordinates, including portions outside the crop. Reset preserves masks.

Zoom options: Fit width, 25%, 50%, 75%, 100%. Each canvas scrolls independently.
Reduced zoom has screen-pixel granularity; numeric fields provide single-row
crop precision. Invalid intervals are rejected without moving the other boundary.

## Ordering and removal

**Change Order** provides Up/Down and Remove Selected; choose Apply Order to
commit. **Remove Image** beside either displayed filename removes that image
from the project immediately. Source files are never deleted. Remaining crops
and masks survive. Mask undo history clears after removal, reordering, or loading
another project because screenshot indices change.

## PNG parts

The default maximum part height is **20,000 pixels**, editable in the toolbar.
The tool splits at whole manual crop boundaries. A single crop taller than the
limit stays intact in its own oversized part. No rows are dropped or duplicated.

Single output: `stitched_chat_YYYYMMDD_HHMM.png`.
Multiple outputs: `stitched_chat_YYYYMMDD_HHMM_part001.png`, etc.
Projects: `manual_stitch_YYYYMMDD_HHMM.json`.

Presets use local time and are editable. Save dialogs remember the last successful
save directory for the current session.

## Projects and privacy

Version-2 JSON stores paths, dimensions, crop coordinates and masks per image.
Version-1 seam projects convert on load. Keep source files at their recorded
paths; relative paths resolve beside the project. Dimension changes are detected;
replacement images with identical dimensions are not.

Project JSON contains local paths and does not embed images. Do not include
personal screenshots, saved projects, or exported chats in a public repository.
The console currently prints key names, focus details, and modifier diagnostics;
review diagnostic logs before sharing them.

## Limits

Source widths must match. RGB/RGBA sample values outside masks are preserved;
grayscale/palette sources expand losslessly. High-bit or unusual color modes
are rejected. Metadata and color profiles are not copied. Large images require
enough RAM for sources, masked copies and the output part. Saving is explicit.

## Tests

```powershell
py -3 -m unittest discover -s tests -v
```

The included tests use synthetic images and need no display. They cover
coordinate conversion, original-pixel assembly, white masks, cropping, splitting,
validation and project round trips. Windows Tk event tests were also performed
during development; generated event tests do not guarantee every physical
keyboard/desktop environment behaves identically.

## Upload to GitHub

Create a repository and upload the **contents of this folder**, keeping `tests/`
as a subfolder. Commit the source, README, dependency file, launcher, changelog,
and `.gitignore`. Attach the source ZIP to a GitHub Release tagged `v1.0.2` if
you want a downloadable release asset. No repository or release is published
by this package itself.

## License

No redistribution license has been selected. Choose and add a `LICENSE` file
before inviting reuse or contributions. Making a repository public by itself
does not grant an open-source license.

## Build the Windows executable

On Windows with Python 3.10+ installed, run `build_windows.cmd`. The generated
`dist/ManualScreenshotStitcher.exe` bundles its runtime. The windowed entry point
disables console-only debug output. Distribute third-party notices alongside the
binary, as in the Windows release package.
