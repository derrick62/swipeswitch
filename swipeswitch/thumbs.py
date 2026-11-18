"""Stage 2 thumbnail extension point; thumbnails are disabled in v1."""
def capture_thumbnail(*args, **kwargs):
    return None
