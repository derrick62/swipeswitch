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

## Window switcher presentation update

- Reworked the switcher into a wider, structured carousel with a heading, live
  position counter, and gesture hint.
- Increased card size and spacing, added a dedicated app-icon preview area,
  clearer typography, and stronger selected-card styling in both themes.
- Added horizontal scrolling and automatic scrolling of the selected card so
  large window lists remain browsable without shrinking every card.
- Window preview areas currently use application icons; live window thumbnails
  remain a separate future enhancement because thumbnail capture is disabled.
