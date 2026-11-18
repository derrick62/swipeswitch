# SwipeSwitch — Technical Audit and Core Preview Status

**Audit basis:** initial source archive and integrated core-preview source, inspected 18 November 2026.  
**Execution status:** static inspection only; the application and test suite were not executed as part of this audit.

## Keep

- `events.py`: immutable, normalised gesture-event data shared by input and recognition.
- `tracker.py`: libwnck-based window discovery and MRU tracking are a suitable starting point.
- `activator.py`: focused activation helper with a fallback is worth retaining.
- `overlay.py`: GTK overlay provides a functional starting presentation.
- `config.py`: TOML configuration is appropriate, although its schema is still prototype-level.
- Existing tests: preserve and expand them.

## Improve

- `listener.py`: support the observed optional sequence number in update events; detect `pointer gesture` devices; accept one or multiple finger counts at the listener boundary; avoid an unread stderr pipe; make process shutdown more deterministic. The application now configures both three- and four-finger input streams.
- `gestures.py`: maintain one authoritative runtime gesture lifecycle; do not keep a second unused state machine.
- `tracker.py`: strengthen eligibility checks and handling of windows that disappear or change state.
- `activator.py`: verify activation outcomes and preserve safe fallback behaviour.
- `overlay.py`: evolve into distinct switcher and Task View presentation components.
- `config.py`: migrate to feature-specific configuration sections with clear validation and migration behaviour.
- Installer: launch the package as a module rather than executing `__main__.py` directly.

## Restructure

`__main__.py` currently owns startup, callbacks, feature coordination, config reload and shutdown. Feature coordination has moved into `controller.py`, with dedicated gesture, desktop, workspace and Task View modules. Further separation and error recovery remain candidates for refinement.

## Missing

- Live/animated preview refresh and performance profiling; current previews are one-shot X11 snapshots captured when the overview opens.
- Structured logging/diagnostics and broader integration tests.
- Complete project documentation and release workflow.

## Corrections included in this audit update

- Parser accepts swipe update lines with and without an optional sequence number.
- Automatic device detection recognises `pointer gesture` capability and prefers a device whose name includes `touchpad`.
- Listener accepts one or multiple finger counts, redirects unused child stderr, and has more deterministic process shutdown.
- Initial threshold-crossing movement contributes to the selected index.
- Installer launcher invokes `python3 -m swipeswitch` with the installed package on `PYTHONPATH`.
- Regression tests were added for the event format variations and threshold-crossing selection.

## Core-preview implementation update

The 0.2.0 core preview adds `gestures.py`, `controller.py`, `workspaces.py`, `desktop.py` and `task_view.py`. MRU tracking now reads the newly active Wnck window rather than treating the signal argument (the previously active window) as the new one. The application now routes three-finger horizontal gestures to the switcher, three-finger vertical gestures to Task View or Show Desktop/restoration, and four-finger horizontal gestures to workspace navigation. A timeout path cancels unfinished gestures rather than committing them.

## Engineering corrections in the 0.2.1 working revision

- Removed the unused parallel state machine; the runtime recogniser is the single gesture-processing path, and `GestureEvent` lives in `events.py`.
- Corrected Show Desktop restoration so the previously active window is reactivated only when it belonged to the original visible-window snapshot.
- Made Wnck loading lazy and explicitly require Wnck 3.0, allowing pure tracker tests to collect without PyGObject installed.
- Explicitly require GTK 3.0, Gdk 3.0, Pango 1.0 and Wnck 3.0 before imports, with the underlying dependency error included in diagnostics.
- Task View now stores XIDs and resolves a live window before activation, avoiding activation through stale Wnck references.
- Reject invalid workspace directions.
- Implemented the existing `use_unaccelerated` setting when libinput provides both movement pairs.
- A new BEGIN cancels an unfinished horizontal switch before starting another gesture.
- Corrected the reversal test: after moving one item left, a net displacement one item right of the origin requires two rightward selection steps.

## Verification status

The 0.3.1 working tree passes 35 automated tests and Python bytecode compilation. This environment does not have PyGObject, so live GTK/libwnck integration, `--check` in an X11 session, and target-device acceptance remain unverified. Run the suite and live checks on the target Kali/XFCE/X11 laptop before treating the preview as stable.


## 0.3.1 visual and gesture refinement

- The switcher now uses a rounded translucent container over a locally blurred/dimmed desktop snapshot, large 16:9 preview cards in a horizontal scrolling strip, application identity/title, selected-card emphasis and a position counter.
- Task View uses the same best-effort X11 snapshot capture with icon fallback.
- Rightward three-finger movement advances through the displayed MRU sequence; leftward movement goes to the previous item.
- Four-finger horizontal navigation now consumes swipe distance incrementally, supports reversal and short-flick fallback, and retains non-wrapping workspace boundaries.
- `GdkX11`/foreign-window capture is optional and was not runtime-verified in this build environment because PyGObject is unavailable here.


## 0.3.2 selection-feedback refinement

The switcher now identifies the highlighted destination in three simultaneous ways: a high-contrast selected-card outline, a “SELECTED” badge on that card's preview, and a live “Switching to: [window title]” label. The position counter remains visible. These changes are confined to `overlay.py`; gesture and desktop-action modules are unchanged. Automated tests do not replace a live GTK/X11 visual check.
