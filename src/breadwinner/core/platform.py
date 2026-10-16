"""Cross-platform system and process utilities for Breadwinner."""

import os
import platform
import subprocess
from pathlib import Path
from typing import Union


def open_path(path: Union[str, Path]) -> bool:
    """Open a file or directory in the operating system's default file manager or viewer.

    - Darwin (macOS): uses 'open'
    - Windows: uses os.startfile with a fallback to subprocess 'explorer'
    - Linux / BSD: uses 'xdg-open'
    """
    target = Path(path).resolve()
    target_str = str(target)
    sys_name = platform.system()

    try:
        if sys_name == "Darwin":
            subprocess.run(["open", target_str], check=False)
            return True
        elif sys_name == "Windows":
            if hasattr(os, "startfile"):
                try:
                    os.startfile(target_str)  # type: ignore[attr-defined]
                    return True
                except Exception:
                    pass
            subprocess.run(["explorer", target_str], check=False)
            return True
        else:
            subprocess.run(["xdg-open", target_str], check=False)
            return True
    except Exception:
        return False
