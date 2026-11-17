"""Create isolated test workspaces without permanently deleting their contents."""

from contextlib import contextmanager
from tempfile import mkdtemp


@contextmanager
def temporary_directory():
    # Retain the workspace so cleanup can use the operating system's Trash.
    yield mkdtemp(prefix="steam-localizer-test-")
