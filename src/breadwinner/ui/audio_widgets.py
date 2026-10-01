"""8-Bit Retro Bakery Audio Widgets & Interactive Push-to-Talk Dictation Modal."""

import time
import math
import random
from pathlib import Path
from typing import Optional, List, Dict, Any

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal, Center
from textual.widgets import Static, Label, Button, TextArea
from textual.screen import ModalScreen
from textual import work

from breadwinner.core.audio import (
    AudioRecorder,
    AudioRecordingSession,
    AudioTranscriber,
    AudioBackendInfo
)


AUDIO_MODAL_CSS = """
AudioDictationModal {
    align: center middle;
    background: rgba(0, 0, 0, 0.75);
}

#dictation-container {
    width: 88;
    height: auto;
    max-height: 90%;
    background: #16161E;
    border: heavy #D18F52;
    padding: 1 2;
}

#dictation-header-title {
    text-align: center;
    color: #FFB86C;
    text-style: bold;
    margin-bottom: 0;
}

#dictation-backend-badge {
    text-align: center;
    margin-bottom: 1;
}

#dictation-status-box {
    height: 1;
    text-align: center;
    text-style: bold;
    margin-bottom: 1;
}

#waveform-box {
    height: 3;
    background: #0C0E14;
    border: round #2A2E3D;
    padding: 0 1;
    content-align: center middle;
    margin-bottom: 1;
}

#vu-meter-box {
    height: 1;
    content-align: center middle;
    margin-bottom: 1;
}

#dictation-timer-label {
    text-align: center;
    color: #94A3B8;
    margin-bottom: 1;
}

#dictation-output-area {
    height: 6;
    background: #0C0E14;
    border: round #D18F52;
    color: #F8F8F2;
    margin-bottom: 1;
}

#dictation-action-bar {
    height: 3;
    align: center middle;
}

#dictation-action-bar Button {
    margin: 0 1;
    min-width: 18;
}

#btn-record-toggle {
    background: #d90429;
    color: #ffffff;
    border: heavy #ef233c;
    text-style: bold;
}

#btn-record-toggle.recording {
    background: #f59e0b;
    color: #000000;
    border: heavy #fbbf24;
}

#btn-accept-dictation {
    background: #1b4332;
    color: #d8f3dc;
    border: heavy #52b788;
    text-style: bold;
}

#btn-cancel-dictation {
    background: #1e293b;
    color: #94a3b8;
    border: heavy #475569;
}
"""


class AudioWaveformWidget(Static):
    """Animated 8-bit retro soundwave visualizer."""

    BARS = [" ", "▂", "▃", "▄", "▅", "▆", "▇", "█"]

    def __init__(self, id: Optional[str] = "audio-waveform"):
        super().__init__("", id=id)
        self.state: str = "idle"  # 'idle', 'recording', 'transcribing', 'done'
        self.frame: int = 0
        self.width_bars: int = 36

    def set_state(self, state: str) -> None:
        self.state = state
        self.refresh_display()

    def advance_frame(self) -> None:
        self.frame += 1
        self.refresh_display()

    def refresh_display(self) -> None:
        if self.state == "idle":
            wave = " ".join(["▂", "▃", "▃", "▂", " "] * 7)
            self.update(f"[dim #334155]{wave}[/dim]")
        elif self.state == "recording":
            # Generate animated sinusoidal + random organic soundwave
            chars = []
            for i in range(self.width_bars):
                phase = (i + self.frame * 2) * 0.4
                base = (math.sin(phase) + 1.0) / 2.0  # 0 to 1
                noise = random.uniform(0.1, 0.4)
                level = min(1.0, max(0.0, (base * 0.7) + noise))
                bar_idx = min(len(self.BARS) - 1, int(level * len(self.BARS)))
                chars.append(self.BARS[bar_idx])
            wave = "".join(chars)
            self.update(f"[bold #50FA7B]{wave}[/bold #50FA7B]")
        elif self.state == "transcribing":
            # Flowing amber baking pulse
            symbols = ["░", "▒", "▓", "█", "▓", "▒", "░"]
            shift = self.frame % len(symbols)
            pattern = [symbols[(i + shift) % len(symbols)] for i in range(self.width_bars)]
            wave = "".join(pattern)
            self.update(f"[bold #FFB86C]{wave}[/bold #FFB86C]")
        elif self.state == "done":
            wave = "".join(["█", "▇", "▆", "▅", "▄", "▃", "▂", " "] * 4)
            self.update(f"[bold #50FA7B]{wave}[/bold #50FA7B]")


class AudioVUMeterWidget(Static):
    """Retro arcade peak VU level meter."""

    def __init__(self, id: Optional[str] = "audio-vu-meter"):
        super().__init__("", id=id)
        self.level: float = 0.0  # 0.0 to 1.0

    def update_level(self, level: float) -> None:
        self.level = max(0.0, min(1.0, level))
        total_blocks = 32
        filled = int(self.level * total_blocks)
        empty = total_blocks - filled

        # Triple-zone TrueColor: green -> amber -> red peak
        g_len = min(filled, 20)
        a_len = min(max(0, filled - 20), 8)
        r_len = max(0, filled - 28)

        bar = (
            f"[bold #50fa7b]{'█' * g_len}[/]"
            f"[bold #ffb86c]{'█' * a_len}[/]"
            f"[bold #ff5555]{'█' * r_len}[/]"
            f"[#334155]{'░' * empty}[/]"
        )
        db = int(-40 + (self.level * 40))
        self.update(f"MIC LEVEL: {bar} [dim]{db:>3} dB[/dim]")


class AudioDictationModal(ModalScreen[Optional[str]]):
    """Universal Push-to-Talk and Audio Dictation Modal for Breadwinner."""

    DEFAULT_CSS = AUDIO_MODAL_CSS

    BINDINGS = [
        ("space", "toggle_recording", "Record / Stop"),
        ("enter", "accept_transcript", "Accept"),
        ("r", "retry_recording", "Retry"),
        ("escape", "cancel_dictation", "Cancel"),
    ]

    def __init__(
        self,
        prompt_title: str = "Voice Dictation & Strategy Brain Dump",
        initial_text: str = "",
        placeholder: str = "Speak naturally... your voice will be transcribed into verified career facts."
    ):
        super().__init__()
        self.prompt_title = prompt_title
        self.initial_text = initial_text
        self.placeholder = placeholder
        self.backend_info: AudioBackendInfo = AudioTranscriber.detect_backend()
        self.session: Optional[AudioRecordingSession] = None
        self.temp_wav: Optional[Path] = None
        self.is_recording: bool = False
        self.is_transcribing: bool = False
        self.waveform_timer = None

    def compose(self) -> ComposeResult:
        with Vertical(id="dictation-container"):
            yield Label(f"[REC] {self.prompt_title.upper()}", id="dictation-header-title")
            
            badge_color = "#50fa7b" if self.backend_info.kind in ["local", "cloud"] else "#ffb86c"
            yield Label(f"[{badge_color}]● STT Engine: {self.backend_info.description}[/{badge_color}]", id="dictation-backend-badge")

            yield Label("[bold #f1fa8c]● READY (Press Space or Click Record to Start)[/bold #f1fa8c]", id="dictation-status-box")

            with Center(id="waveform-box"):
                yield AudioWaveformWidget(id="dictation-waveform")

            with Center(id="vu-meter-box"):
                yield AudioVUMeterWidget(id="dictation-vu-meter")

            yield Label("00:00 / 01:00 (Hold Space or Click Stop when finished)", id="dictation-timer-label")

            yield TextArea(self.initial_text, id="dictation-output-area", show_line_numbers=False)

            with Horizontal(id="dictation-action-bar"):
                yield Button("● Record (Space)", variant="error", id="btn-record-toggle")
                yield Button("✓ Accept & Insert (Enter)", variant="success", id="btn-accept-dictation")
                yield Button("✕ Cancel (Esc)", variant="default", id="btn-cancel-dictation")

    def on_mount(self) -> None:
        # Start animation pulse timer
        self.waveform_timer = self.set_interval(0.1, self._on_tick)
        self.query_one("#dictation-output-area", TextArea).focus()

    def _on_tick(self) -> None:
        try:
            wf = self.query_one("#dictation-waveform", AudioWaveformWidget)
            wf.advance_frame()

            if self.is_recording and self.session:
                elapsed = self.session.get_elapsed_seconds()
                mins = int(elapsed // 60)
                secs = int(elapsed % 60)
                self.query_one("#dictation-timer-label", Label).update(f"REC: {mins:02d}:{secs:02d} / 01:00 (Press Space to Stop)")

                # Simulate dynamic natural speech audio level
                vu = self.query_one("#dictation-vu-meter", AudioVUMeterWidget)
                base = 0.45 + (0.35 * math.sin(elapsed * 4)) + random.uniform(-0.1, 0.15)
                vu.update_level(base)
        except Exception:
            pass

    def action_toggle_recording(self) -> None:
        if self.is_transcribing:
            return

        if not self.is_recording:
            self._start_recording()
        else:
            self._stop_recording_and_transcribe()

    def _start_recording(self) -> None:
        self.is_recording = True
        btn = self.query_one("#btn-record-toggle", Button)
        btn.label = "■ Stop & Transcribe (Space)"
        btn.add_class("recording")

        status = self.query_one("#dictation-status-box", Label)
        status.update("[bold #ff5555]● RECORDING AUDIO... (Speak clearly into microphone)[/bold #ff5555]")

        wf = self.query_one("#dictation-waveform", AudioWaveformWidget)
        wf.set_state("recording")

        # Start non-blocking recording session
        self.session = AudioRecorder.create_session()
        self.session.start()

    def _stop_recording_and_transcribe(self) -> None:
        if not self.session:
            return

        self.is_recording = False
        self.is_transcribing = True

        btn = self.query_one("#btn-record-toggle", Button)
        btn.label = "⏳ Transcribing..."
        btn.remove_class("recording")

        status = self.query_one("#dictation-status-box", Label)
        status.update(f"[bold #ffb86c]⏳ TRANSCRIBING VIA {self.backend_info.name.upper()}...[/bold #ffb86c]")

        wf = self.query_one("#dictation-waveform", AudioWaveformWidget)
        wf.set_state("transcribing")

        vu = self.query_one("#dictation-vu-meter", AudioVUMeterWidget)
        vu.update_level(0.0)

        # Stop audio recording session
        self.session.stop()
        audio_path = self.session.output_wav

        # Background worker transcription
        self._async_transcribe(audio_path)

    @work(thread=True)
    def _async_transcribe(self, audio_path: Path) -> None:
        """Run speech-to-text transcription in background thread."""
        try:
            transcript = AudioTranscriber.transcribe(audio_path)
        except Exception as e:
            transcript = f"Transcription error: {str(e)}"

        self.app.call_from_thread(self._on_transcription_complete, transcript)

    def _on_transcription_complete(self, transcript: str) -> None:
        self.is_transcribing = False
        wf = self.query_one("#dictation-waveform", AudioWaveformWidget)
        wf.set_state("done")

        status = self.query_one("#dictation-status-box", Label)
        status.update("[bold #50fa7b]✓ TRANSCRIBED SUCCESSFULLY! (Review & press Enter to accept)[/bold #50fa7b]")

        btn = self.query_one("#btn-record-toggle", Button)
        btn.label = "● Re-Record"

        editor = self.query_one("#dictation-output-area", TextArea)
        existing = editor.text.strip()
        if existing:
            editor.text = f"{existing} {transcript}"
        else:
            editor.text = transcript

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-record-toggle":
            self.action_toggle_recording()
        elif event.button.id == "btn-accept-dictation":
            self.action_accept_transcript()
        elif event.button.id == "btn-cancel-dictation":
            self.action_cancel_dictation()

    def action_retry_recording(self) -> None:
        if self.is_transcribing:
            return
        if self.session and self.session.is_recording:
            self.session.stop()
        self.query_one("#dictation-output-area", TextArea).text = ""
        self._start_recording()

    def action_accept_transcript(self) -> None:
        text = self.query_one("#dictation-output-area", TextArea).text.strip()
        self.dismiss(text if text else None)

    def action_cancel_dictation(self) -> None:
        if self.session and self.session.is_recording:
            self.session.stop()
        self.dismiss(None)
