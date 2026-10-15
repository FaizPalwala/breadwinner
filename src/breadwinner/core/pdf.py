"""PDF export engine using native headless browser printing."""

import os
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional


class PDFGenerationError(Exception):
    """Raised when PDF generation fails."""
    pass


class BrowserNotFoundError(PDFGenerationError):
    """Raised when no compatible browser executable is found."""
    pass


def find_browser_executable(configured_path: Optional[str] = None) -> Optional[str]:
    """Locate a Chromium-based browser executable across macOS, Linux, and Windows."""
    # 1. User-configured override
    if configured_path and Path(configured_path).exists():
        return configured_path

    env_path = os.environ.get("CHROME_PATH") or os.environ.get("BROWSER_PATH")
    if env_path and Path(env_path).exists():
        return env_path

    system = platform.system()

    # 2. macOS common application paths
    if system == "Darwin":
        mac_candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Arc.app/Contents/MacOS/Arc",
            os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            os.path.expanduser("~/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"),
        ]
        for candidate in mac_candidates:
            if Path(candidate).is_file() and os.access(candidate, os.X_OK):
                return candidate

    # 3. Linux / BSD common paths and binaries
    elif system == "Linux":
        linux_bins = [
            "google-chrome-stable",
            "google-chrome",
            "chromium-browser",
            "chromium",
            "brave-browser",
            "microsoft-edge-stable",
        ]
        for b in linux_bins:
            which_path = shutil.which(b)
            if which_path:
                return which_path

        linux_static_candidates = [
            "/usr/bin/google-chrome-stable",
            "/usr/bin/google-chrome",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/snap/bin/chromium",
        ]
        for candidate in linux_static_candidates:
            if Path(candidate).is_file() and os.access(candidate, os.X_OK):
                return candidate

    # 4. Windows common paths
    elif system == "Windows":
        win_candidates = [
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe"),
        ]
        for candidate in win_candidates:
            if Path(candidate).is_file():
                return candidate

    # 5. Generic PATH fallback
    for generic in ["google-chrome", "chromium", "chrome", "edge"]:
        path = shutil.which(generic)
        if path:
            return path

    return None


def render_html_to_pdf(
    html_path: Path,
    output_pdf_path: Path,
    open_after: bool = False,
    browser_path: Optional[str] = None
) -> Path:
    """Render an HTML file to a print-optimized ATS PDF using a headless browser."""
    html_path = html_path.resolve()
    if not html_path.exists():
        raise FileNotFoundError(f"Source HTML file not found: {html_path}")

    output_pdf_path = output_pdf_path.resolve()
    output_pdf_path.parent.mkdir(parents=True, exist_ok=True)

    browser = find_browser_executable(browser_path)
    if not browser:
        raise BrowserNotFoundError(
            "Could not locate Google Chrome, Chromium, Brave, or Edge.\n"
            "Please install Google Chrome or set BROWSER_PATH in your .env file."
        )

    with tempfile.TemporaryDirectory() as user_data_dir:
        cmd = [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            f"--user-data-dir={user_data_dir}",
            "--no-pdf-header-footer",
            f"--print-to-pdf={output_pdf_path}",
            f"file://{html_path}"
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=45
            )
        except subprocess.TimeoutExpired:
            raise PDFGenerationError("Headless browser timed out after 45 seconds while rendering PDF.")
        except Exception as e:
            raise PDFGenerationError(f"Failed to execute headless browser: {e}")

        if not output_pdf_path.exists() or output_pdf_path.stat().st_size == 0:
            err_msg = result.stderr.strip() if result.stderr else "Unknown browser error"
            raise PDFGenerationError(f"PDF was not generated. Output: {err_msg}")

    if open_after:
        open_file_in_viewer(output_pdf_path)

    return output_pdf_path


def open_file_in_viewer(file_path: Path) -> None:
    """Open a file in the user's default system viewer."""
    system = platform.system()
    try:
        if system == "Darwin":
            subprocess.run(["open", str(file_path)], check=False)
        elif system == "Windows":
            os.startfile(str(file_path))  # type: ignore
        else:
            subprocess.run(["xdg-open", str(file_path)], check=False)
    except Exception:
        pass


def bake_application_package(
    app_dir: Path,
    open_after: bool = False,
    browser_path: Optional[str] = None
) -> dict:
    """Bake both resume.pdf and cover_letter.pdf (if present) for an application directory."""
    results = {
        "success": False,
        "resume_pdf": None,
        "resume_size_kb": None,
        "size_kb": None,
        "cover_letter_pdf": None,
        "cover_letter_size_kb": None,
        "errors": []
    }
    app_dir = Path(app_dir).resolve()
    resume_html = app_dir / "resume.html"
    resume_pdf = app_dir / "resume.pdf"
    if resume_html.exists():
        try:
            render_html_to_pdf(resume_html, resume_pdf, open_after=open_after, browser_path=browser_path)
            results["resume_pdf"] = resume_pdf
            results["resume_size_kb"] = round(resume_pdf.stat().st_size / 1024, 1)
            results["size_kb"] = results["resume_size_kb"]
            results["success"] = True
        except Exception as e:
            results["errors"].append(f"Resume PDF error: {e}")

    letter_html = app_dir / "cover_letter.html"
    letter_md = app_dir / "cover_letter.md"
    letter_pdf = app_dir / "cover_letter.pdf"

    if not letter_html.exists() and letter_md.exists():
        try:
            from breadwinner.core.renderer import TemplateRenderer
            from breadwinner.core.portfolio import JsonResumeAdapter
            from breadwinner.config import settings
            from breadwinner.core.pantry import PantryManager

            pantry = PantryManager(settings.pantry_dir)
            profile = None
            if (app_dir / "resume.json").exists():
                try:
                    profile = JsonResumeAdapter(app_dir / "resume.json").load_profile()
                except Exception:
                    pass
            if not profile and pantry.is_initialized():
                profile = pantry.load_profile()

            if profile:
                md_txt = letter_md.read_text(encoding="utf-8")
                renderer = TemplateRenderer()
                parts = app_dir.name.split("_")
                comp = parts[1] if len(parts) >= 2 else None
                titl = parts[2] if len(parts) >= 3 else None
                html_txt = renderer.render_cover_letter_html(
                    profile,
                    cover_letter_text=md_txt,
                    company=comp,
                    title=titl
                )
                letter_html.write_text(html_txt, encoding="utf-8")
        except Exception as e:
            results["errors"].append(f"Cover letter HTML generation error: {e}")

    if letter_html.exists():
        try:
            render_html_to_pdf(letter_html, letter_pdf, open_after=False, browser_path=browser_path)
            results["cover_letter_pdf"] = letter_pdf
            results["cover_letter_size_kb"] = round(letter_pdf.stat().st_size / 1024, 1)
        except Exception as e:
            results["errors"].append(f"Cover Letter PDF error: {e}")

    return results

