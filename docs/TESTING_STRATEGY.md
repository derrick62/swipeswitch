# SwipeSwitch Testing Strategy

## Test layers

**Unit tests** exercise pure parsing, recognition, routing, window eligibility and state transitions without requiring GTK or a live desktop.

**Integration tests** exercise libwnck, GTK main-loop dispatch, XFCE/xfwm4 workspace operations, X11 activation and packaging in a real session.

**Manual acceptance tests** verify the actual touchpad and the complete interaction from finger movement through desktop response.

## Current regression coverage to preserve

- BEGIN, UPDATE and END parsing.
- UPDATE lines with and without optional sequence numbers.
- Labelled and slash-pair movement formats.
- Cancellation and malformed input.
- Gesture lifecycle, selection wrap, quick flick and timeout.
- MRU ordering and current-workspace/sticky filtering.

## Planned gesture-engine coverage

- Three- and four-finger event streams.
- Positive/negative horizontal and vertical movement.
- Accumulated displacement across multiple updates.
- Threshold boundaries and diagonal/ambiguous gestures.
- Exactly-once routing.
- Cancellation, missing END, timeout and rapid successive gestures.
- Unsupported finger counts are ignored.

## Planned feature coverage

- Window switcher: MRU order, wrapping, minimized windows, closing windows, cancellation and stale references.
- Workspace navigation: direction, first/last workspace boundaries and no duplicate action per gesture.
- Show Desktop: visible-only snapshot, already-minimized windows, repeated down gesture, closed windows and restoration.
- Task View: zero/one/many windows, pointer selection, activation, Escape and outside-click dismissal.

## Manual acceptance matrix

Test with normal, minimized, maximized, fullscreen and sticky windows; multiple workspaces; a range of window counts; slow, fast, short, long, diagonal and cancelled gestures; repeated Show Desktop; Task View dismissal; touchpad disconnect/reconnect; and extended daily use.

## Evidence labels

Every milestone report should distinguish: **implemented**, **unit-tested**, **integration-tested**, and **manually verified**. Never report a stronger status than the evidence supports.
