"""Unit tests for terminal geometry auto-detection and preset sizing."""

from breadwinner.ui.geometry import (
    get_display_resolution,
    get_preset_geometry,
    resize_terminal_window,
)


def test_get_display_resolution():
    """Verify display resolution scanner returns plausible dimensions."""
    w, h = get_display_resolution()
    assert isinstance(w, int)
    assert isinstance(h, int)
    assert w >= 800
    assert h >= 600


def test_get_preset_geometries():
    """Verify standard geometries for split, normal, and full presets."""
    cols_split, rows_split = get_preset_geometry("split")
    assert cols_split >= 80
    assert rows_split >= 30

    cols_norm, rows_norm = get_preset_geometry("normal")
    assert cols_norm == 120
    assert rows_norm == 36

    cols_full, rows_full = get_preset_geometry("full")
    assert cols_full >= cols_norm
    assert rows_full >= rows_norm


def test_resize_terminal_window_safe():
    """Ensure resize_terminal_window executes safely without raising exceptions."""
    # Should safely try escape sequences/AppleScript and not crash in test runner
    success = resize_terminal_window(120, 36)
    assert isinstance(success, bool)
