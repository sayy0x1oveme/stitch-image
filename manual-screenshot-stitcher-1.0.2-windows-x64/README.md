# Manual Screenshot Stitcher 1.0.2 — Windows x64

## Run

Extract this ZIP, then double-click **ManualScreenshotStitcher.exe**.
No Python installation, PowerShell command, or dependency installation is needed.
The app includes Python, Pillow and Tcl/Tk. Initial startup extracts its runtime
to a temporary directory and may take a few seconds. Keep screenshots and saved
projects outside that temporary directory.

## Use

1. Select Screenshots. Each image starts with its whole height included.
2. CROP Mode: left-click sets START, right-click sets END. Numeric fields offer
   precise edits. Each screenshot keeps its own crop coordinates.
3. MASK Mode: left-drag draws a solid white rectangle without holding Shift.
   Use Shift (Auto) restores the temporary Shift-drag workflow.
4. Click a mask to select it, Delete removes it, Ctrl+Z undoes mask changes.
5. Preview Seam checks the join. Save Project stores crops and masks in JSON.
6. Remove Image excludes a screenshot without deleting the source file.
7. Build Final Image validates crops and exports original-resolution PNGs.

Default maximum PNG height: 20,000 pixels. Splits occur at whole screenshot crop
boundaries. A single oversized crop stays intact in its own part. Source widths
must match. Keep source files available when reopening projects.

This executable is unsigned. Windows may show an unrecognized-publisher prompt;
verify where you obtained the file and its SHA-256 checksum before running it.
This is a Windows x64 build, tested on Windows 11. It is not a macOS/Linux app.

## Release contents

- ManualScreenshotStitcher.exe — self-contained desktop application.
- README.md — these instructions.
- THIRD_PARTY/ — notices for bundled runtimes and libraries.

Publish this ZIP as a GitHub Release asset. The source package can remain in the
repository. No screenshots, saved projects, or personal chat exports are included.
The application itself has no selected redistribution license yet; select a
license separately if you intend to grant reuse rights.

## Verification

The built EXE passed its embedded checks with Python/Tcl environment variables
cleared: bundled Pillow, original pixel assembly, opaque masks, coordinates,
split groups, Tcl/Tk GUI initialization, mode buttons and screenshot removal.
This is a smoke test, not a guarantee across all Windows installations.
