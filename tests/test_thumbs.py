from swipeswitch.thumbs import capture_thumbnail


class FakeWindow:
    def get_xid(self):
        return 123


def test_thumbnail_capture_degrades_cleanly_without_x11_bindings():
    # Unit-test environments commonly have no GTK/GdkX11 runtime. Preview
    # failure must remain non-fatal and let the UI use the app icon instead.
    assert capture_thumbnail(FakeWindow(), object()) is None
