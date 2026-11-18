# Changelog

All notable project changes are documented here.

## [0.1.0-audit] — 2026-11-18

### Changed
- Made the libinput parser accept swipe update events with an optional sequence number.
- Updated automatic touchpad detection for `pointer gesture` capability reports.
- Allowed the listener to filter multiple finger counts.
- Redirected unused libinput child stderr and strengthened listener shutdown.
- Applied threshold-crossing movement to the first visible switcher selection.
- Corrected the installed launcher to invoke the package as a module.
- Added the master product/architecture document, roadmap, audit and testing strategy.

### Verification
- Static source inspection completed. Automated and live desktop tests remain pending.


## 0.2.0 — Core feature preview

- Added a unified three-/four-finger gesture recognizer and central controller.
- Added four-finger virtual workspace navigation.
- Added Show Desktop snapshots and restoration of previously visible windows.
- Added a persistent, clickable Task View overview.
- Connected three-finger horizontal switching to the shared gesture pipeline.
- Added focused gesture-recognition unit tests.
- Updated project documentation and configuration for the core preview.
- Not yet verified on the target Kali/XFCE laptop.


## [Unreleased] — Engineering corrections

- Consolidated gesture lifecycle ownership in the runtime recogniser and moved normalised events to `events.py`.
- Fixed Show Desktop restoration to avoid activating a window outside the original snapshot.
- Made Wnck import lazy and version-specific so non-desktop unit tests can run without PyGObject.
- Added explicit GTK/Gdk/Pango/Wnck namespace version requirements and clearer dependency diagnostics.
- Made Task View resolve selected XIDs against the live window list before activation.
- Rejected invalid workspace directions.
- Implemented selection of libinput's unaccelerated movement values when configured.
- Cancelled an unfinished horizontal switch when a new gesture begins.
- Added regression coverage for restoration, workspaces, timeouts, gesture restarts and unaccelerated parsing.
- Corrected the reversal test to reflect cumulative selection semantics.

### Verification
- 27 automated tests passed in the available environment.
- Python compilation passed.
- Live Kali/XFCE/X11 and physical touchpad validation remain outstanding.


## 0.3.0 — Preview-first switcher and workspace refinement

- Corrected horizontal selection direction so a rightward swipe advances to the next displayed window and a leftward swipe moves to the previous one.
- Replaced the small icon strip with a centered, full-monitor dimmed overview.
- Added best-effort X11 window snapshots using GDK foreign-window capture.
- Added 16:9 preview tiles, application identity/title, selection emphasis and scroll-to-selection for large window sets.
- Added graceful icon fallback for minimized, unmapped or inaccessible windows.
- Applied the same preview-first treatment to Task View.
- Retained four-finger left/right workspace navigation and added regression coverage that a multi-update swipe emits exactly one workspace action.
- Updated documentation and bumped the project version to 0.3.0.

### Verification
- Automated tests and Python compilation run in the packaging environment; live X11 preview capture and physical four-finger gesture behavior still require verification on the target Kali/XFCE laptop.


## 0.3.1 — Horizontal switcher and continuous workspace navigation

- Replaced the multi-row preview grid with a horizontal card strip and horizontal scrolling.
- Increased card dimensions and spacing; each card has a dedicated 16:9 preview area with application icon and title beneath it.
- Added a translucent rounded container, a locally captured blurred desktop backdrop when Pillow/X11 capture is available, and a graceful dimmed-overlay fallback.
- Added a high-contrast selected card and a live selected-position counter.
- Changed four-finger workspace navigation to consume swipe distance incrementally, support mid-gesture reversals, and retain a one-workspace short-flick fallback.
- Preserved existing three-finger gesture routing and window activation behaviour.
- Added Pillow to the Debian/Kali installer for desktop-backdrop blur.

### Verification
- 35 automated tests pass, Python bytecode compilation passes, and a wheel builds successfully using the available local build tools.
- Live GTK/X11 rendering, compositor behaviour, and physical touchpad feel still require validation on the target laptop.


## 0.3.2 — Explicit switcher selection feedback

- Added a prominent “SELECTED” badge directly on the currently highlighted window preview.
- Strengthened the selected card border and contrast in both dark and light themes.
- Added a live “Switching to: [window title]” label so the destination remains clear while browsing.
- Kept the position counter and horizontal auto-scroll synchronized with the selected card.
- No gesture recognition, window tracking, activation, Task View, or Show Desktop logic changed.

### Verification
- Automated tests and Python bytecode compilation are run for this release. GTK rendering and physical touchpad acceptance still require testing on the target Kali/XFCE/X11 laptop.
