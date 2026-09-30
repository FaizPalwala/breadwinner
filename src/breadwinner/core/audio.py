"""Cross-platform Audio & Voice-First Input (STT) for Breadwinner.

Provides a unified speech-to-text pipeline that prioritizes local-first processing
and gracefully falls back across operating systems and hardware architectures:

1. Local Apple Silicon (macOS arm64): `mlx-whisper` via Metal / Apple Neural Engine.
2. Local Linux / Windows / x86_64: `faster-whisper` or `whisper` via CTranslate2 / CPU.
3. Universal BYOK Cloud Fallback:
   - Groq Cloud Whisper (`whisper-large-v3`, ~0.15s latency, near-zero cost)
   - OpenAI Whisper (`whisper-1`)
   - Gemini Audio Multimodal
4. Zero-Dependency Audio Recording:
   - Uses `sounddevice` if installed, or system `ffmpeg` (avfoundation/alsa/dshow).
"""

import os
import sys
import shutil
import platform
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass

from breadwinner.config import settings


@dataclass
class AudioBackendInfo:
    """Information about an audio transcription backend."""
    name: str  # 'mlx-whisper', 'faster-whisper', 'whisper', 'groq-whisper', 'openai-whisper', 'mock', 'none'
    kind: str  # 'local', 'cloud', 'mock', 'none'
    available: bool
    description: str


class AudioTranscriber:
    """Discovers, selects, and executes speech-to-text transcription."""

    def __init__(self, backend_override: Optional[str] = None):
        self.backend_override = backend_override

    @classmethod
    def detect_backend(cls) -> AudioBackendInfo:
        """Detect the highest-priority working STT backend on this system."""
        # 1. Check local Apple Silicon mlx-whisper
        if platform.system() == "Darwin" and platform.machine() == "arm64":
            try:
                import mlx_whisper  # noqa: F401
                return AudioBackendInfo(
                    name="mlx-whisper",
                    kind="local",
                    available=True,
                    description="100% Local Apple Silicon Metal / Neural Engine (mlx-whisper)"
                )
            except ImportError:
                pass

        # 2. Check local faster-whisper (Linux, Windows, Intel/AMD, x86_64)
        try:
            import faster_whisper  # noqa: F401
            return AudioBackendInfo(
                name="faster-whisper",
                kind="local",
                available=True,
                description="100% Local CTranslate2 Engine (faster-whisper)"
            )
        except ImportError:
            pass

        # 3. Check local openai-whisper
        try:
            import whisper  # noqa: F401
            return AudioBackendInfo(
                name="whisper",
                kind="local",
                available=True,
                description="100% Local PyTorch Engine (openai-whisper)"
            )
        except ImportError:
            pass

        # 4. Check BYOK Groq Whisper (Ultra-low latency cloud STT)
        if getattr(settings, "groq_api_key", None):
            return AudioBackendInfo(
                name="groq-whisper",
                kind="cloud",
                available=True,
                description="BYOK Groq Cloud (whisper-large-v3, ~150ms latency)"
            )

        # 5. Check BYOK OpenAI Whisper
        if getattr(settings, "openai_api_key", None):
            return AudioBackendInfo(
                name="openai-whisper",
                kind="cloud",
                available=True,
                description="BYOK OpenAI Cloud (whisper-1)"
            )

        # 6. Check Gemini Audio
        if getattr(settings, "gemini_api_key", None):
            return AudioBackendInfo(
                name="gemini-audio",
                kind="cloud",
                available=True,
                description="BYOK Google Gemini Audio"
            )

        # 7. Mock / Unavailable
        if getattr(settings, "breadwinner_llm_provider", "") == "mock":
            return AudioBackendInfo(
                name="mock",
                kind="mock",
                available=True,
                description="Breadwinner Mock Audio Transcriber"
            )

        return AudioBackendInfo(
            name="none",
            kind="none",
            available=False,
            description="No local Whisper installed and no BYOK Cloud keys configured"
        )

    @classmethod
    def discover_groq_whisper_model(cls, api_key: Optional[str] = None) -> str:
        """Query Groq live in the background to discover and select the best available Whisper STT model."""
        key = api_key or getattr(settings, "groq_api_key", None)
        if not key:
            return "whisper-large-v3"
        try:
            import requests
            resp = requests.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {key}"},
                timeout=3.0
            )
            if resp.status_code == 200:
                raw_models = resp.json().get("data", [])
                m_ids = [m["id"] for m in raw_models if isinstance(m, dict) and "id" in m and "whisper" in m["id"].lower()]
                for target in ["whisper-large-v3-turbo", "whisper-large-v3"]:
                    if target in m_ids:
                        return target
                if m_ids:
                    return m_ids[0]
        except Exception:
            pass
        return "whisper-large-v3"

    @classmethod
    def _transcribe_impl(cls, audio_path: Path, backend_override: Optional[str] = None) -> str:
        """Transcribe an audio file (.wav, .mp3, .m4a) to text."""
        path = Path(audio_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {path}")

        backend = backend_override or cls.detect_backend().name

        if backend == "mock":
            return "Led cloud migration to Kubernetes across 3 AWS regions, reducing p99 latency by 45ms."

        if backend == "mlx-whisper":
            import mlx_whisper
            result = mlx_whisper.transcribe(str(path), path_or_hf_repo="mlx-community/whisper-tiny")
            return result.get("text", "").strip()

        if backend == "faster-whisper":
            from faster_whisper import WhisperModel
            model = WhisperModel("tiny", device="cpu", compute_type="int8")
            segments, _ = model.transcribe(str(path))
            return " ".join(s.text.strip() for s in segments).strip()

        if backend == "whisper":
            import whisper
            model = whisper.load_model("tiny")
            result = model.transcribe(str(path))
            return result.get("text", "").strip()

        if backend == "groq-whisper":
            import requests
            api_key = settings.groq_api_key
            headers = {"Authorization": f"Bearer {api_key}"}
            whisper_model = cls.discover_groq_whisper_model(api_key)
            with open(path, "rb") as f:
                files = {"file": (path.name, f, "audio/wav")}
                data = {"model": whisper_model}
                resp = requests.post("https://api.groq.com/openai/v1/audio/transcriptions", headers=headers, files=files, data=data, timeout=30)
                resp.raise_for_status()
                return resp.json().get("text", "").strip()

        if backend == "openai-whisper":
            import requests
            api_key = settings.openai_api_key
            headers = {"Authorization": f"Bearer {api_key}"}
            with open(path, "rb") as f:
                files = {"file": (path.name, f, "audio/wav")}
                data = {"model": "whisper-1"}
                resp = requests.post("https://api.openai.com/v1/audio/transcriptions", headers=headers, files=files, data=data, timeout=30)
                resp.raise_for_status()
                return resp.json().get("text", "").strip()

        raise RuntimeError(
            f"No working audio STT backend found for '{backend}'. "
            "Install 'mlx-whisper' (Mac) / 'faster-whisper' (Linux/Windows) or set GROQ_API_KEY in .env."
        )

    class _TranscribeDispatcher:
        def __get__(self, obj, objtype=None):
            if obj is None:
                return objtype._transcribe_impl
            return lambda audio_path, backend_override=None: objtype._transcribe_impl(
                audio_path, backend_override or getattr(obj, "backend_override", None)
            )

    transcribe = _TranscribeDispatcher()


class AudioRecorder:
    """Lightweight cross-platform audio recorder using system ffmpeg or sounddevice."""

    @staticmethod
    def is_available() -> bool:
        """Check if any recording mechanism (ffmpeg or sounddevice) is available."""
        if shutil.which("ffmpeg"):
            return True
        try:
            import sounddevice  # noqa: F401
            return True
        except ImportError:
            return False

    @staticmethod
    def record_to_file(output_wav: Path, duration_seconds: int = 15) -> bool:
        """Record audio from default mic into a WAV file. Returns True on success."""
        output_wav = Path(output_wav).resolve()
        output_wav.parent.mkdir(parents=True, exist_ok=True)

        # 1. Try sounddevice if installed
        try:
            import sounddevice as sd
            from scipy.io.wavfile import write as write_wav
            sample_rate = 16000
            recording = sd.rec(int(duration_seconds * sample_rate), samplerate=sample_rate, channels=1, dtype='int16')
            sd.wait()
            write_wav(str(output_wav), sample_rate, recording)
            return True
        except ImportError:
            pass

        # 2. Try ffmpeg command line
        ffmpeg_bin = shutil.which("ffmpeg")
        if ffmpeg_bin:
            sys_name = platform.system()
            if sys_name == "Darwin":
                cmd = [
                    ffmpeg_bin, "-y", "-f", "avfoundation", "-i", ":default",
                    "-t", str(duration_seconds), "-ar", "16000", "-ac", "1", str(output_wav)
                ]
            elif sys_name == "Linux":
                cmd = [
                    ffmpeg_bin, "-y", "-f", "alsa", "-i", "default",
                    "-t", str(duration_seconds), "-ar", "16000", "-ac", "1", str(output_wav)
                ]
            elif sys_name == "Windows":
                cmd = [
                    ffmpeg_bin, "-y", "-f", "dshow", "-i", "audio=default",
                    "-t", str(duration_seconds), "-ar", "16000", "-ac", "1", str(output_wav)
                ]
            else:
                return False

            try:
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=duration_seconds + 5)
                return output_wav.exists() and output_wav.stat().st_size > 100
            except Exception:
                return False

        return False
