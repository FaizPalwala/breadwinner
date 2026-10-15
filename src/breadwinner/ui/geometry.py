"""Machine Display Scanner & Cross-Platform Terminal Geometry Controller.

Detects primary display resolution and applies terminal geometry presets:
- Split View: Exactly half display width, vertical stack layout.
- Normal Desktop: Centered 120x36 balanced view.
- Fullscreen: Maximum available display geometry, widescreen layout.
"""

import os
import re
import sys
import shutil
import platform
import subprocess
from typing import Tuple, Optional


def get_display_resolution() -> Tuple[int, int]:
    """Scans the host machine for primary display resolution in points/pixels.
    
    Returns:
        Tuple of (width, height). Falls back to (1440, 900) if detection fails.
    """
    system = platform.system()
    try:
        if system == "Darwin":
            out = subprocess.check_output(
                ["system_profiler", "SPDisplaysDataType"],
                text=True,
                timeout=3,
                stderr=subprocess.DEVNULL
            )
            m = re.search(r"Resolution:\s*(\d+)\s*x\s*(\d+)", out)
            if m:
                w, h = int(m.group(1)), int(m.group(2))
                if "Retina" in out:
                    w, h = max(800, w // 2), max(600, h // 2)
                return w, h

        elif system == "Linux":
            out = subprocess.check_output(
                ["xrandr"],
                text=True,
                timeout=2,
                stderr=subprocess.DEVNULL
            )
            m = re.search(r"\b(\d{3,4})x(\d{3,4})\b.*\*", out)
            if m:
                return int(m.group(1)), int(m.group(2))

        elif system == "Windows":
            cmd = "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width; [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height"
            out = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", cmd],
                text=True,
                timeout=3,
                stderr=subprocess.DEVNULL
            )
            lines = [line.strip() for line in out.splitlines() if line.strip()]
            if len(lines) >= 2 and lines[0].isdigit() and lines[1].isdigit():
                return int(lines[0]), int(lines[1])
    except Exception:
        pass

    return 1440, 900


def get_preset_geometry(preset: str = "normal") -> Tuple[int, int]:
    """Calculates terminal column and row dimensions for a named preset.

    Args:
        preset: 'split', 'normal', or 'full'.

    Returns:
        Tuple of (target_cols, target_rows).
    """
    preset = preset.lower().strip()
    if preset == "normal":
        return 120, 36

    w_pts, h_pts = get_display_resolution()
    # Typical character cell size: ~8.5pt width, ~20pt line height
    if preset == "split":
        cols = max(84, min(100, int((w_pts / 2) / 8.5)))
        rows = max(30, min(48, int((h_pts - 80) / 20)))
        return cols, rows

    if preset == "full":
        cols = max(140, min(220, int(w_pts / 8.5)))
        rows = max(38, min(56, int((h_pts - 60) / 20)))
        return cols, rows

    return 120, 36


def resize_terminal_window(target_cols: int, target_rows: int) -> bool:
    """Resizes the terminal window using platform-specific bridges & ANSI escapes.

    Tries in priority order:
    1. macOS AppleScript (Terminal.app / iTerm2)
    2. ANSI CSI resize sequence (\\033[8;rows;cols t) for Kitty, Alacritty, WezTerm
    3. Windows mode con

    Returns:
        True if an execution attempt was dispatched, False otherwise.
    """
    system = platform.system()
    success = False

    # 1. macOS Native Bridge
    if system == "Darwin":
        term_prog = os.environ.get("TERM_PROGRAM", "").lower()
        if "apple_terminal" in term_prog or term_prog == "terminal":
            try:
                script = (
                    f'tell application "Terminal"\n'
                    f'  set number of columns of front window to {target_cols}\n'
                    f'  set number of rows of front window to {target_rows}\n'
                    f'end tell'
                )
                subprocess.run(["osascript", "-e", script], timeout=1.5, capture_output=True)
                success = True
            except Exception:
                pass
        elif "iterm" in term_prog:
            try:
                script = (
                    f'tell application "iTerm2"\n'
                    f'  tell current session of current window\n'
                    f'    set columns to {target_cols}\n'
                    f'    set rows to {target_rows}\n'
                    f'  end tell\n'
                    f'end tell'
                )
                subprocess.run(["osascript", "-e", script], timeout=1.5, capture_output=True)
                success = True
            except Exception:
                pass

    # 2. ANSI Escape Sequence (Kitty, Alacritty, WezTerm, Ghostty, Linux/X11)
    if sys.stdout.isatty():
        try:
            sys.stdout.write(f"\033[8;{target_rows};{target_cols}t")
            sys.stdout.flush()
            success = True
        except Exception:
            pass

    # 3. Windows mode con fallback
    if system == "Windows":
        try:
            subprocess.run(f"mode con: cols={target_cols} lines={target_rows}", shell=True, timeout=1)
            success = True
        except Exception:
            pass

    return success


def sync_app_sidebar(app) -> None:
    """Synchronize collapsed vs expanded visual styling of the app sidebar."""
    try:
        from textual.widgets import Button
        sidebar = app.query_one("#app-sidebar")
        toggle_btn = app.query_one("#btn-sidebar-toggle", Button)
        btn_bb = app.query_one("#btn-sidebar-breadbox", Button)
        btn_st = app.query_one("#btn-sidebar-studio", Button)
        btn_pa = app.query_one("#btn-sidebar-pantry", Button)
        btn_mod = app.query_one("#btn-sidebar-model", Button)
        blade = app.query_one("#blade-sidebar-engine")
        btn_set = app.query_one("#btn-sidebar-settings", Button)

        if app.sidebar_collapsed:
            sidebar.add_class("-collapsed")
            toggle_btn.label = "►"
            btn_bb.label = "▣"
            btn_st.label = "♨"
            btn_pa.label = "▤"
            btn_mod.styles.display = "none"
            blade.styles.display = "block"
            blade.update_provider(app.get_active_provider_name())
            btn_set.label = "[§]"
        else:
            sidebar.remove_class("-collapsed")
            toggle_btn.label = "◄"
            btn_bb.label = "▣ Breadbox (1)"
            btn_st.label = "♨ Studio (2)"
            btn_pa.label = "▤ Pantry (3)"
            btn_mod.styles.display = "block"
            blade.styles.display = "none"
            btn_set.label = "[§] Settings"
    except Exception:
        pass


def apply_app_layout_preset(app, preset: str, resize_window: bool = True) -> None:
    """Adapt the TUI layout to a target preset geometry (split, normal, full)."""
    from textual.widgets import Button, Label
    app.layout_preset = preset.lower()
    cols, rows = get_preset_geometry(app.layout_preset)
    app._last_width = cols
    app._update_quick_keys_hint(cols)
    if resize_window:
        resize_terminal_window(cols, rows)

    try:
        cycle_btn = app.query_one("#btn-app-cycle-preset", Button)
        if app.layout_preset == "split":
            cycle_btn.label = "⛶ Split"
        elif app.layout_preset in ("full", "fullscreen"):
            cycle_btn.label = "⛶ Full"
        else:
            cycle_btn.label = "⛶ Normal"
    except Exception:
        pass

    try:
        sidebar = app.query_one("#app-sidebar")
        top_pills = app.query_one("#top-bar-nav-pills")
        screen_title = app.query_one("#top-bar-screen-title")
        toggle_btn = app.query_one("#btn-sidebar-toggle")
        model_chip = app.query_one("#btn-active-model-chip", Button)
        pipeline_box = app.query_one("#pipeline-container")
        lab_split = app.query_one("#studio-lab-split")
        toggle_stack_btn = app.query_one("#btn-lab-toggle-stack", Button)
        quit_btn = app.query_one("#btn-app-quit", Button)
        brand = app.query_one("#top-bar-brand", Label)

        if app.layout_preset == "split":
            sidebar.styles.display = "none"
            top_pills.styles.display = "block"
            screen_title.styles.display = "none"
            toggle_btn.styles.display = "none"
            model_chip.styles.display = "block"
            model_chip.label = f"● {app.get_active_provider_name()} ▾"
            quit_btn.label = "✕ (q)"
            brand.update("[bold #FFB86C]◈ BREADWINNER[/]")
            pipeline_box.add_class("-vertical-stack")
            lab_split.add_class("-vertical-stack")
            toggle_stack_btn.label = "Side-by-Side"
        else:
            sidebar.styles.display = "block"
            top_pills.styles.display = "none"
            screen_title.styles.display = "block"
            toggle_btn.styles.display = "block"
            model_chip.styles.display = "none"
            quit_btn.label = "✕ Quit (q)"
            brand.update("[bold #FFB86C]◈ BREADWINNER[/]")
            pipeline_box.remove_class("-vertical-stack")
            lab_split.remove_class("-vertical-stack")
            toggle_stack_btn.label = "Stack"
            sync_app_sidebar(app)
    except Exception:
        pass

    if resize_window:
        app.notify(f"Layout adapted to {app.layout_preset.upper()} ({cols}×{rows})", title="Terminal Geometry")

