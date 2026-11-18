# SwipeSwitch Development Roadmap

The project is developed through controlled milestones. A milestone closes only when its exit conditions have been verified and the implementation status has been documented.

| Milestone | Scope | Exit condition |
|---|---|---|
| 0 — Baseline and audit | Inspect existing code, correct critical baseline defects, integrate documentation, establish workflow and backlog | Repository and technical baseline are understood; critical issues are addressed or explicitly tracked |
| 1 — Gesture foundation | Listener, parser, normalised events, recogniser, thresholds, cancellation, timeout and router | Supported gestures are recognised and routed exactly once in automated tests |
| 2 — Window switching | Eligible windows, MRU, live selection, activation and minimized-window handling | Three-finger horizontal switching works on the target desktop |
| 3 — Workspace navigation | Workspace discovery, direction, boundaries and gesture integration | Four-finger horizontal navigation works without duplicate actions |
| 4 — Show Desktop | Visible-window snapshot, hide and safe restoration | Previously visible windows are restored without restoring previously minimized windows |
| 5 — Task View | Persistent grid, selection, activation and dismissal | Task View behaves independently from the horizontal switcher |
| 6 — Visual refinement | Icons, thumbnails, layout, animation, themes and monitor considerations | UI is coherent and responsive; thumbnails remain optional |
| 7 — Integration and reliability | Cross-feature testing, conflicts, recovery, logging and performance | Complete gesture set works together reliably |
| 8 — Packaging | Installation, configuration, startup, diagnostics and uninstall | Fresh install/configure/launch/uninstall workflow is reproducible |
| 9 — Release | Versioning, release notes, compatibility and maintenance process | Documented release candidate meets release checklist |

## Development cycle

1. Understand the requirement and acceptance criteria.
2. Design component responsibilities and interfaces.
3. Implement focused changes.
4. Run automated tests and live desktop verification where required.
5. Document changes, evidence, limitations and remaining work.

Do not equate implementation with verification. Unit tests, integration tests and manual hardware verification are recorded separately.


## Core-preview implementation update (0.2.0)

The first integrated core implementation now includes the gesture recognizer,
three-finger window switching, four-finger workspace navigation, Show Desktop
snapshot/restore, and Task View. The implementation is a functional preview;
no live-desktop acceptance verification is claimed yet. The next development
pass is integration testing and defect correction across all six gesture paths.
Visual polish, thumbnails and packaging hardening remain subsequent work.
