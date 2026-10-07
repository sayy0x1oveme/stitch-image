# Changelog

## 1.0.2 — 2026-10-08

- Add a self-contained Windows x64 executable; users need no Python installation.
- Add a windowed entry point, embedded runtime smoke test, and reproducible build script.


## 1.0.1 — 2026-10-08

- Fix debug f-string quote syntax to support Python 3.10 and 3.11.
- Check Python version and Pillow/Tkinter before launch, with actionable error messages.
- No changes to crop, masking or export behavior.

## 1.0.0 — 2026-10-07

First packaged source release of the standalone manual tool.

- Per-image START/END crops and original-resolution PNG rendering.
- Manual opaque-white masks, deletion and mask undo.
- CROP/MASK buttons with optional Shift mode and diagnostics.
- Zoom, scrolling, seam preview and persistent JSON projects.
- Screenshot ordering and removal without source-file deletion.
- Whole-crop output splitting, default 20,000-pixel maximum part height.
- Timestamped save names and session save-directory memory.
