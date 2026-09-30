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
